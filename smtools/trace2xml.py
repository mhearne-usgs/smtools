#!/usr/bin/env python

import warnings
warnings.filterwarnings("ignore")

#stdlib imports
import sys
import os.path
from datetime import datetime

#third party imports
from obspy import read
from obspy.signal.invsim import seisSim, cornFreq2Paz
from obspy.xseed.parser import Parser
from neicio.tag import Tag
import matplotlib.pyplot as plt
from matplotlib import dates

FILTER_FREQ = 0.02
CORNERS = 4

def smPSA(data, samp_rate):
    """
    ShakeMap pseudo-spectral parameters

    Compute 5% damped PSA at 0.3, 1.0, and 3.0 seconds.

    Data must be an acceleration Trace

    :type data: :class:`obspy.trace`
    :param data: Data in acceleration to convolve with pendulum at freq.
    :type delta: float
    :param delta: sample rate (samples per sec)
    :rtype: (float, float, float)
    :return: PSA03, PSA10, PSA30
    """

    D = 0.05	# 5% damping

    out = []
    periods = [0.3, 1.0, 3.0]
    for T in periods:
        freq = 1.0 / T
        omega = (2 * 3.14159 * freq) ** 2

        paz_sa = cornFreq2Paz(freq, damp=D)
        paz_sa['sensitivity'] = omega
        paz_sa['zeros'] = []
        dd = seisSim(data.data, samp_rate, paz_remove=None, paz_simulate=paz_sa,
                     taper=True, simulate_sensitivity=True, taper_fraction=0.05)

        if abs(max(dd)) >= abs(min(dd)):
            psa = abs(max(dd))
        else:
            psa = abs(min(dd))
        out.append(psa)

    return out

def amps2xml(stationlist,outfolder,netsource):
    '''
    stationlist - list of station dictionaries.  Each station has fields:
     - lat
     - lon
     - code
     - name
     - channels - dictionary of dictionaries, where keys are channel names, and values are:
       - pga
       - pgv
       - psa03
       - psa10
       - psa30
    '''
    stationlist_tag = Tag('stationlist',attributes={'created':datetime.utcnow().strftime('%s')})
    for station in stationlist:
        name = station['name']
        code = station['code']
        net,sta = code.split('.')
        lat = station['lat']
        lon = station['lon']
        instrument = ''
        source = netsource
        channels = station['channels']
        stationtag = Tag('station',attributes={'code':code,'name':sta,
                                               'insttype':instrument,'source':netsource,
                                               'netid':net,'commtype':'DIG',
                                               'lat':lat,'lon':lon,
                                               'loc':name})
        for channelkey,channeldict in channels.iteritems():
            comptag = Tag('comp',attributes={'name':channelkey})
            pga = channeldict['pga']
            pgv = channeldict['pgv']
            psa03 = channeldict['psa03']
            psa10 = channeldict['psa10']
            psa30 = channeldict['psa30']
            psa03tag = Tag('psa03',attributes={'value':psa03})
            psa10tag = Tag('psa10',attributes={'value':psa10})
            psa30tag = Tag('psa30',attributes={'value':psa30})
            acctag = Tag('acc',attributes={'value':pga})
            veltag = Tag('vel',attributes={'value':pgv})
            comptag.addChild(acctag)
            comptag.addChild(veltag)
            comptag.addChild(psa03tag)
            comptag.addChild(psa10tag)
            comptag.addChild(psa30tag)
            stationtag.addChild(comptag)
        stationlist_tag.addChild(stationtag)

    outfile = os.path.join(outfolder,'%s_dat.xml' % netsource)
    print 'Saving to %s' % outfile
    stationlist_tag.renderToXML(filename=outfile,ntabs=1)
    return (outfile,stationlist_tag)
            

def trace2xml(traces,parser,outfolder,netsource,doPlot=False,seedresp=None):
    """
    Calibrate accelerometer data, derive peak ground motion values, and write a ShakeMap-compatible data file.

    Takes a sequence of ObsPy Trace objects and an ObsPy Parser (such as from a dataless SEED file) and
    calibrates the data in the Traces, derives peak ground motions for each (pga,pgv,psa) and then 
    writes those data to a ShakeMap-compatible XML data file.
    
    @param traces - Sequence of ObsPy Trace objects, containing acceleration data in units of m/s^2.
    @param parser - ObsPy Parser object.  Can also be None, in which case calibration step is NOT performed, and station coordinates will have to be present in the input traces.
    @param outfolder - Path (string) where output data XML files and QA plots should be written.
    @param netsource - Name of data source (knet, geonet, etc.)
    """
    if parser is not None:
        vdict = parser.getInventory()
    else:
        vdict = None
    #Make the top level tag - stationlist
    stationlist_tag = Tag('stationlist',attributes={'created':datetime.utcnow().strftime('%s')})
    first_station = 1
    current_tag = ''
    plotfiles = []
    hfmt = dates.DateFormatter('%H:%M:%S') #used for formatting dates in plots
    for trace in traces:
        net = trace.stats['network']
        station = trace.stats['station']
        location = trace.stats['location']
        channel = trace.stats['channel']
        channel_id = '%s.%s.%s.%s' % (net,station,location,channel)
        if parser is not None:
            paz = parser.getPAZ(channel_id)
            coordinates = parser.getCoordinates(channel_id)
        else:
            try:
                coordinates = {'latitude':trace.stats['lat'],
                               'longitude':trace.stats['lon'],
                               'elevation':trace.stats['height']}
            except:
                sys.stderr.write('Could not get station coordinates from trace object of station %s\n' % station)
                continue

        #If we have separate calibration data, apply it here
        if parser is not None:
            trace.simulate(paz_remove=paz,remove_sensitivity=True,simulate_sensitivity=False)
            trace.stats['units'] = 'acc' #ASSUMING THAT ANY SAC DATA IS ACCELERATION!
        else:
            if seedresp is None:
                raise Exception('Must have a PolesAndZeros data structure (i.e., from dataless SEED) or a RESP file.')
            else:
                pre_filt = (0.01, 0.02, 20, 30)
                try:
                    trace.simulate(paz_remove=None, pre_filt=pre_filt, seedresp=seedresp)
                except Exception,error:
                    pass
            
        #make the component tag to hold the measurements
        comptag = Tag('comp',attributes={'name':channel})
        if trace.stats['units'] == 'acc':
            delta = trace.stats['sampling_rate']
            trace.detrend('linear')
            trace.detrend('demean')
            trace.taper(max_percentage=0.05, type='cosine')
            
            
            trace.filter('highpass',freq=FILTER_FREQ,zerophase=True,corners=CORNERS)
            
            trace.detrend('linear')
            trace.detrend('demean')

            # Get the Peak Ground Acceleration
            pga = abs(trace.max())

            (psa03, psa10, psa30) = smPSA(trace, delta)

            #convert accelerations to %g
            psa03 = psa03/0.0981
            psa10 = psa10/0.0981
            psa30 = psa30/0.0981
            pga = pga/0.0981

            #make the tags for the individual measurements, add them to comp tag
            psa03tag = Tag('psa03',attributes={'value':psa03})
            psa10tag = Tag('psa10',attributes={'value':psa10})
            psa30tag = Tag('psa30',attributes={'value':psa30})
            acctag = Tag('acc',attributes={'value':pga})

            comptag.addChild(acctag)
            comptag.addChild(psa03tag)
            comptag.addChild(psa10tag)
            comptag.addChild(psa30tag)
            
            #plot the acceleration (top) and velocity
            if doPlot:
                plt.clf()
                ax1 = plt.subplot(2,1,1)
                atimes = trace.times()
                atimes = [(trace.stats['starttime'] + t).datetime for t in atimes]
                matimes = dates.date2num(atimes)
                plt.plot(matimes,trace.data)
                ax1.xaxis.set_major_locator(dates.MinuteLocator())
                ax1.xaxis.set_major_formatter(hfmt)
                plt.title('Acceleration %s' % channel_id)
                plt.ylabel('$m/s^2$')
                plt.xticks([])
                #labels = ax1.get_xticklabels()
                #ax1.set_xticklabels( labels, rotation=45 ) ;

        if trace.stats['units'] == 'vel': #don't integrate the broadband
            vtimes = trace.times()
            vtimes = [(trace.stats['starttime'] + t).datetime for t in vtimes]
            mvtimes = dates.date2num(vtimes)
            vtrace = trace.copy()
        else:
            vtrace = trace.copy()
            vtrace.integrate() # vtrace now has velocity
            vtimes = vtrace.times()
            vtimes = [(vtrace.stats['starttime'] + t).datetime for t in vtimes]
            mvtimes = dates.date2num(vtimes)
        if doPlot:
            if trace.stats['units'] == 'acc':
                ax2 = plt.subplot(2,1,2)
            else:
                ax2 = plt.subplot(1,1,1)
            plt.plot(mvtimes,vtrace.data)
            ax2.xaxis.set_major_locator(dates.MinuteLocator())
            ax2.xaxis.set_major_formatter(hfmt)
            plt.title('Velocity %s' % channel_id)
            plt.ylabel('$m/s$')
            plt.xticks(rotation=30)
            pngfile = os.path.join(outfolder,'%s.png' % channel_id)
            plt.savefig(pngfile)
            plotfiles.append(pngfile)
            plt.close()

        # Get the Peak Ground Velocity
        pgv = abs(vtrace.max())

        #convert velocity to cm/s
        pgv = pgv * 100

        #make the tags for the individual measurements
        veltag = Tag('vel',attributes={'value':pgv})
        comptag.addChild(veltag)

        code = '%s.%s' % (net,station)
        if current_tag == code:		# Same station: just add the comp tag
            stationtag.addChild(comptag)
        else:				# New station: start a new station tag
            if not first_station:	# Close out the previous station
                stationlist_tag.addChild(stationtag)
            station_name = 'UNK'
            if vdict is not None:
                for sta in vdict['stations']:
                    if sta['station_id'] == '%s.%s' % (net,station):
                        station_name = sta['station_name']
                        break
                instrument = 'UNK'
                for cha in vdict['channels']:
                    if cha['channel_id'] == channel_id:
                        instrument = cha['instrument']
                        break
                source = ''
                for netw in vdict['networks']:
                    if netw['network_code'] == net:
                        source = netw['network_name']
                        break
            else:
                station_name = trace.stats['station']
                instrument = ''
                source = ''
            lat = coordinates['latitude']
            lon = coordinates['longitude']
            stationtag = Tag('station',attributes={'code':code,'name':station_name,
                                                   'insttype':instrument,'source':source,
                                                   'netid':net,'commtype':'DIG',
                                                   'lat':lat,'lon':lon,
                                                   'loc':station_name})
            stationtag.addChild(comptag)
            current_tag = code
            first_station = 0

    if not first_station:	# Add the final station to the list
        stationlist_tag.addChild(stationtag)
    outfile = os.path.join(outfolder,'%s_dat.xml' % netsource)
    print 'Saving to %s' % outfile
    stationlist_tag.renderToXML(filename=outfile,ntabs=1)
    return (outfile,plotfiles,stationlist_tag)

if __name__ == '__main__':
    # seedfile = sys.argv[1]
    # sacfiles = sys.argv[2:]
    # parser = Parser(seedfile)
    # traces = []
    # for sacfile in sacfiles:
    #     stream = read(sacfile)
    #     traces.append(stream[0])
    # outfile,pltofiles,tag = trace2xml(traces,parser,os.getcwd(),doPlot=True)
    station1 = {'lat':43.25,'lon':23.76,'code':'US.HVS','name':'Freds Garage',
                'channels':{
                    'HHN':{'pga':23.1,'pgv':10.2,
                           'psa03':11.8,'psa10':12.9,'psa30':13.1},
                    'HHE':{'pga':23.1,'pgv':10.2,
                           'psa03':11.8,'psa10':12.9,'psa30':13.1},
                    'HHZ':{'pga':23.1,'pgv':10.2,
                           'psa03':11.8,'psa10':12.9,'psa30':13.1}}}
    stationlist = [station1]
    outfile,stag = amps2xml(stationlist,os.getcwd(),'us')
                           
                           
                                   
                                   
    
