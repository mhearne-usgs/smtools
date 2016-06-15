#!/usr/bin/env python

#stdlib imports
import sys
import datetime
import os.path
import re
import pickle

#third party
from obspy import read, Stream
from obspy.fdsn import Client as FDSN_Client
from obspy.iris.client import Client as IrisClient
from obspy.xseed.parser import Parser
from obspy.core.util import NamedTemporaryFile
from obspy import UTCDateTime
from obspy.core.util import geodetics
from obspy.core import AttribDict

#Kate's IRIS data fetcher code
#from reviewData import reviewData

#local imports
from .fetcher import StrongMotionFetcher,StrongMotionFetcherException
from .trace2xml import trace2xml

TIMEFMT = '%Y-%m-%dT%H:%M:%S'
RADIUS = 3.6 #degrees within which to search for stations
WAVERATE = 1 #km/s assumed slowest rate for wave propagation to nearfield stations

def unique_list(seq):  # make a list only contain unique values and keep their order
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

def getdata(network, station, location, channel, t1, t2, attach_response=True,
            savedat=False, folderdat='data', filenamepref='Data_', clientname='IRIS',
            loadfromfile=False, reloadfile=False):
    """
    Get data from IRIS (or NCEDC) if it exists, save it
    USAGE
    st = getdata(network, station, location, channel, t1, t2, attach_response=True,
            savedat=False, folderdat='data', filenamepref='Data_', clientname='IRIS',
            loadfromfile=False)

    INPUTS
    network - seismic network codes, comma separated and no spaces Example: 'NF,IW,RE,TA,UU'
    station - station names, comma separated and no spaces Example: 'BFR,WOY,TCR,WTM'
    location - location codes, comma separated and no spaces Example: '01,00' or more commonly, just use '*' for all
    channel - channels to use. Example: 'BHZ,BHE,BHN,EHZ'
    t1 - UTCDateTime(starttime)
    t2 - UTCDateTime(endtime)
    attach_response - attach station response info?
    savedat - True or False, save data locally so it doesn't need to be redownloaded to look at it again
    folderdat - folder in which to save data, if you save it
    filenamepref - prefix for filename, if you are saving data
    clientname - source of data from FDSN webservices: 'IRIS','NCEDC', 'GEONET' etc. - see list here http://docs.obspy.org/archive/0.10.2/packages/obspy.fdsn.html
    loadfromfile - True or False - if a file from this time period is already on the computer, if you say True, it will automatically use that file without asking if you want to use it

    OUTPUTS
    st_ordered - ObsPy stream object that is in the same order as input station list
    """
    #create directory if need be
    if not os.path.exists(folderdat) and savedat is True:
        os.makedirs(folderdat)
    #create file name
    #filename = filenamepref+str(t1)+str(t2)
    filename = filenamepref+t1.strftime('%Y-%m-%dT%H%M')+'_'+t2.strftime('%Y-%m-%dT%H%M')
    #see if it exists already
    if os.path.exists(folderdat+'/'+filename):
        if loadfromfile is True:
            choice = 'Y'
        else:
            if reloadfile is False:
                choice = raw_input('file already exists for this time period, enter Y to load from file, N to reload\n')
            else:
                choice = 'N'
    else:
        choice = 'N'
    if choice.upper() == 'Y':
        st_ordered = read(folderdat+'/'+filename, format='PICKLE')
    else:
        try:
            client = FDSN_Client(clientname)
            st = client.get_waveforms(network, station, location, channel,
                                      t1, t2, attach_response=True)
            try:
                st.merge(fill_value='interpolate')
            except:
                print('bulk merge failed, trying station by station')
                st_new = Stream()
                stationlist = unique_list([trace.stats.station for trace in st])
                for sta in stationlist:
                    temp = st.select(station=sta)
                    try:
                        temp.merge(fill_value='interpolate')
                        st_new += temp
                    except Exception as e:
                        print(e)
                        print('%s would not merge - deleting it') % (sta,)
                st = st_new
            st.detrend('linear')
            #find min start time
            mint = min([trace.stats.starttime for trace in st])
            st.trim(starttime=mint, pad=True, fill_value=0)
        except Exception as e:
            print(e)
            return
        #make sure it's in the same order as it was originally input
        order = [trace.stats.station for trace in st]
        st_ordered = Stream()
        temp = station.split(',')
        for sta in temp:
            while sta in order:
                indx = order.index(sta)
                st_ordered.append(st[indx])
                st.pop(indx)
                try:
                    order = [trace.stats.station for trace in st]
                except:
                    order = ['', '']
        #save files
        if savedat:
            st_ordered.write(folderdat+'/'+filename, format="PICKLE")
    return st_ordered

def getpeaks(st, pga=True, pgv=True, psa=True, periods=[0.3, 1.0, 3.0], damping=0.05, cosfilt=None, water_level=60., csvfile=None, verbal=False):
    """
    Performs station correction (st must have response info attached to it) - removes trends and tapers with 5 percent cosine taper before doing station correction, adds as field in st and prints out results, option to save csv file
    All values in m/s and/or m/s**2
    USAGE

    INPUTS
    st - stream of obspy traces of raw seismic data with response information attached - best if visually inspected in case there are data problems
    pga - True if want to calculate pga
    pgv - True if want to calculate pgv
    psa - True if want to calculate peak spectral accelerations
    periods - periods at which to calculate psa
    damping - damping to use for psa calculations
    cosfilt - tuple of four corners, in Hz, for cosine filter to use in station correction. None for no cosine filter
    water_level - water level to use in station correction
    csvfile - full file path of csvfile to output with results, None if don't want to output csvfile
    verbal - if True, will print out all results to screen

    OUTPUTS
    stacc - stream of data corrected to acceleration with pga's, pgv's and psa's attached, stored as AttribDict in in tr.stats.gmparam
    csvfile
    stvel - stream of data corrected to velocity with pga's, pgv's and psa's attached, stored as AttribDict in in tr.stats.gmparam
    """
    from obspy.core import AttribDict

    st.detrend('demean')
    st.detrend('linear')
    st.taper(max_percentage=0.05, type='cosine')

    # If coordinates aren't already attached, try to attach from IRIS
    if 'coordinates' not in st[0].stats:
        try:
            st = attach_coords_IRIS(st)  # Attach lats and lons if available
        except:
            print('Could not attach lats and lons, continuing')

    stacc = st.copy()
    # Build place to store gm parameters
    for trace in stacc:
        trace.stats.gmparam = AttribDict()

    try:
        stacc.remove_response(output='ACC', pre_filt=cosfilt, water_level=water_level)
    except:
        print('Failed to do bulk station correction, trying one at a time')
        stacc = st.copy()  # Start with fresh data
        removeid = []
        for trace in stacc:
            try:
                trace.remove_response(output='ACC', pre_filt=cosfilt, water_level=water_level)
            except:
                print('Failed to remove response for %s, deleting this station' % (trace.stats.station + trace.stats.channel,))
                removeid.append(trace.id)
        for rmid in removeid:  # Delete uncorrected ones
            for tr in stacc.select(id=rmid):
                stacc.remove(tr)

    stvel = st.copy()
    # Build place to store gm parameters
    for trace in stvel:
        trace.stats.gmparam = AttribDict()
    try:
        stvel.remove_response(output='VEL', pre_filt=cosfilt, water_level=water_level)
    except:
        print('Failed to do bulk station correction, trying one at a time')
        stvel = st.copy()  # Start with fresh data
        removeid = []
        for trace in stvel:
            try:
                trace.remove_response(output='VEL', pre_filt=cosfilt, water_level=water_level)
            except:
                print('Failed to remove response for %s, deleting this station' % (trace.stats.station + trace.stats.channel,))
                removeid.append(trace.id)
        for rmid in removeid:  # Delete uncorrected ones
            for tr in stvel.select(id=rmid):
                stvel.remove(tr)

    if pga is True:
        for j, trace in enumerate(stacc):
            trace.stats.gmparam['pga'] = np.abs(trace.max())  # in obspy, max gives the max absolute value of the data
            stvel[j].stats.gmparam['pga'] = np.abs(trace.max())
            if verbal is True:
                print('%s - PGA = %1.3f m/s') % (trace.id, np.abs(trace.max()))

    if pgv is True:
        for j, trace in enumerate(stvel):
            trace.stats.gmparam['pgv'] = np.abs(trace.max())
            stacc[j].stats.gmparam['pgv'] = np.abs(trace.max())
            if verbal is True:
                print('%s - PGV = %1.3f m/s') % (trace.id, np.abs(trace.max()))

    if psa is True:
        for j, trace in enumerate(stacc):
            out = []
            for T in periods:
                freq = 1.0/T
                omega = (2 * 3.14159 * freq) ** 2
                paz_sa = cornFreq2Paz(freq, damp=damping)
                paz_sa['sensitivity'] = omega
                paz_sa['zeros'] = []
                dd = seisSim(trace.data, trace.stats.sampling_rate, paz_remove=None, paz_simulate=paz_sa,
                             taper=True, simulate_sensitivity=True, taper_fraction=0.05)
                if abs(max(dd)) >= abs(min(dd)):
                    psa1 = abs(max(dd))
                else:
                    psa1 = abs(min(dd))
                out.append(psa1)
                if verbal is True:
                    print('%s - PSA at %1.1f sec = %1.3f m/s^2') % (trace.id, T, psa1)
            trace.stats.gmparam['periods'] = periods
            trace.stats.gmparam['psa'] = out
            stvel[j].stats.gmparam['periods'] = periods
            stvel[j].stats.gmparam['psa'] = out

    if csvfile is not None:
        import csv
        with open(csvfile, 'wb') as csvfile1:
            writer = csv.writer(csvfile1)
            writer.writerow(['Id']+[tr.id for tr in st])
            try:
                test = [tr.stats.coordinates['latitude'] for tr in st]
                writer.writerow(['Lat']+[tr.stats.coordinates['latitude'] for tr in st])
                writer.writerow(['Lon']+[tr.stats.coordinates['longitude'] for tr in st])
            except:
                print('Could not print out lats/lons to csvfile')
            if pga is True:
                writer.writerow(['PGA (m/s^2)']+[tr.stats.gmparam['pga'] for tr in stacc])
            if pgv is True:
                writer.writerow(['PGV (m/s)']+[tr.stats.gmparam['pgv'] for tr in stvel])
            if psa is True:
                for k, period in enumerate(periods):
                    writer.writerow(['PSA (m/s^2) at %1.1f sec, %1.0fpc damping' % (period, 100*damping)]+[tr.stats.gmparam['psa'][k] for tr in stacc])

    return stacc, stvel

def getepidata(event_lat, event_lon, event_time, tstart=-5., tend=200., minradiuskm=0., maxradiuskm=20., channels='*', location='*', source='IRIS'):
    """
    Automatically pull existing data within a certain distance of the epicenter (or any lat/lon coordinates) and attach station coordinates to data
    USAGE
    st = getepidata(event_lat, event_lon, event_time, tstart=-5., tend=200., minradiuskm=0., maxradiuskm=20., channels='*', location='*', source='IRIS')
    INPUTS
    event_lat = latitude of event in decimal degrees
    event_lon = longitude of event in decimal degrees
    event_time = Event time in UTC in any format obspy's UTCDateTime can parse - e.g. '2016-02-05T19:57:26'
    tstart = number of seconds to add to event time for start time of data (use negative number to start before event_time)
    tend = number of seconds to add to event time for end time of data
    radiuskm = radius to search for data
    channels = 'strong motion' to get all strong motion channels (excluding low sample rate ones), 'broadband' to get all broadband instruments, 'short period' for all short period channels, otherwise a single line of comma separated channel codes, * wildcards are okay, e.g. channels = '*N*,*L*'
    location = comma separated list of location codes allowed, or '*' for all location codes
    source = FDSN source, 'IRIS', 'NCEDC', 'GEONET' etc., see list here http://docs.obspy.org/archive/0.10.2/packages/obspy.fdsn.html

    OUTPUTS
    st = obspy stream containing data from within requested area
    """
    event_time = UTCDateTime(event_time)
    client = FDSN_Client(source)

    if channels.lower() == 'strong motion':
        channels = 'EN*,HN*,BN*,EL*,HL*,BL*'
    elif channels.lower() == 'broadband':
        channels = 'BH*,HH*'
    elif channels.lower() == 'short period':
        channels = 'EH*'
    else:
        channels = channels.replace(' ', '')  # Get rid of spaces

    t1 = UTCDateTime(event_time) + tstart
    t2 = UTCDateTime(event_time) + tend

    inventory = client.get_stations(latitude=event_lat, longitude=event_lon, minradius=minradiuskm/111.32, maxradius=maxradiuskm/111.32, channel=channels, level='channel', startbefore=t1, endafter=t2)
    temp = inventory.get_contents()
    netnames = temp['networks']
    stas = temp['stations']
    stanames = [n.split('.')[1].split()[0] for n in stas]

    st = getdata(','.join(unique_list(netnames)), ','.join(unique_list(stanames)), location, channels, t1, t2, attach_response=True, clientname=source)

    if st is None:
        print('No data returned')
        return

    for trace in st:
        try:
            coord = inventory.get_coordinates(trace.id)
            trace.stats.coordinates = AttribDict({'latitude': coord['latitude'], 'longitude': coord['longitude'], 'elevation': coord['elevation']})
        except:
            print('Could not attach coordinates for %s' % trace.id)

    return st

def parseSAC(sacpz):
    sacdict = {}
    pat = pat = "\((.*?)\)"
    lines = sacpz.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('*'):
            parts = line.split(':')
            if len(parts) < 2:
                continue
            value = parts[1].strip()
            key = parts[0].strip('*').strip()
            key = re.sub(pat,'',key).strip()
            sacdict[key] = value
    return sacdict

class IrisFetcher(StrongMotionFetcher):
    def __init__(self,verbose=False):
        self.verbose = verbose

    def fetch(self,lat,lon,etime,radius,timewindow,outfolder):
        """
        Retrieve all strong motion data record files associated with an event.
        @param lat: Latitude associated with event
        @param lon: Longitude associated with event
        @param etime: UTC time of event
        @param radius: Distance window (km) within which to search for events on IRIS.
        @param timewindow: Time window (sec) within which to search for events on IRIS.
        @param outfolder: Folder where retrieved strong motion mini-SEED data files should be written.
        @return: List of strong motion mini-SEED data files.
        """
        etimestr = etime.strftime('%Y-%m-%dT%H:%M:%S')
        st = getepidata(lat, lon, etimestr, tstart=-3,
                                   tend=+timewindow, minradiuskm=0., maxradiuskm=radius,
                                   channels='strong motion', location='*', source='IRIS')
        seedfiles = []
        if st is not None:
            stacc,stvel = getpeaks(st,pga=False,pgv=False,psa=False)
            for trace in stacc:
                isAcc = trace.stats['processing'][-1].lower().find('acc') > -1
                if not isAcc:
                    continue #skip if this isn't an acceleration record
                nscl = '%s_%s_%s_%s.sac' % (trace.stats['network'],trace.stats['station'],
                                             trace.stats['channel'],trace.stats['location'])
                seedfile = os.path.join(outfolder,nscl)
                trace.stats['sac'] = {}
                trace.stats['sac']['stla'] = trace.stats['coordinates']['latitude']
                trace.stats['sac']['stlo'] = trace.stats['coordinates']['longitude']
                trace.stats['sac']['stel'] = trace.stats['coordinates']['elevation']
                trace.write(seedfile,format='SAC')
                seedfiles.append(seedfile)
        return seedfiles

def readiris(seedfile): #trivial, since we saved as a seed file
    trace = read(seedfile)[0]
    #stuff the coordinates back into the main stats dict
    trace.stats['lat'] = trace.stats['sac']['stla']
    trace.stats['lon'] = trace.stats['sac']['stlo']
    trace.stats['height'] = trace.stats['sac']['stel']
    trace.stats['units'] = 'acc'
    return trace
    
if __name__ == '__main__':
    ifetch = IrisFetcher()
    #
    lat = 22.83
    lon = 120.625
    etime = datetime.datetime(2016,2,5,19,57,26)
    outfolder = '/Users/mhearne/tmp/iris'
    dfiles = ifetch.fetch(lat,lon,etime,300,400,outfolder)
    traces = []
    for dfile in dfiles:
        trace = readiris(dfile)
        traces.append(trace)
    
    trace2xml(traces,None,outfolder,'IR')

    
