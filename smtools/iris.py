#!/usr/bin/env python

#stdlib imports
import sys
import datetime
import os.path
import re
import pickle

#third party
from obspy import read
from obspy.fdsn import Client
from obspy.iris.client import Client as IrisClient
from obspy.xseed.parser import Parser
from obspy.core.util import NamedTemporaryFile
from obspy import UTCDateTime
from obspy.core.util import geodetics

#local imports
from fetcher import StrongMotionFetcher,StrongMotionFetcherException,BroadBandFetcher,BroadBandFetcherException

TIMEFMT = '%Y-%m-%dT%H:%M:%S'
RADIUS = 3.6 #degrees within which to search for stations
WAVERATE = 1 #km/s assumed slowest rate for wave propagation to nearfield stations

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
    def __init__(self):
        pass
    
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
        client = Client("IRIS")
        etime = UTCDateTime(etime)
        inventory = client.get_stations(latitude=lat, longitude=lon,maxradius=RADIUS,
                                        starttime=etime,endtime=etime+300,level='channel')
        irisclient = IrisClient()
        datafiles = []
        for channel in inventory.get_contents()['channels']:
            n,s,l,c = channel.split('.')
            if c.startswith('H') or c.startswith('B'):
                try:
                    sacpz = irisclient.sacpz(n,s,l,c)
                except Exception,msg:
                    sys.stderr.write('Error retrieving coordinates for %s: "%s"\n' % (channel,str(msg)))
                    continue
                sacdict = parseSAC(sacpz)
                slat = float(sacdict['LATITUDE'])
                slon = float(sacdict['LONGITUDE'])
                sheight = float(sacdict['ELEVATION'])

                #figure out a time window for this event
                #assume that waves are traveling at 1 km/sec
                distance,az,backaz = geodetics.gps2DistAzimuth(lat, lon, slat, slon)
                distance /= 1000.0
                elapsed = distance/WAVERATE #result in seconds
                endtime = etime + elapsed + 300
                try:
                    st = client.get_waveforms(n,s,l,c, etime, endtime)
                except Exception,msg:
                    sys.stderr.write('Error retrieving waveforms for %s: "%s"\n' % (channel,str(msg)))
                    continue
                sys.stderr.write('Retrieving data for station %s... %.1f km distance\n' % (channel,distance))
                trace = st[0]
                tf = NamedTemporaryFile()
                respf = tf.name
                try:
                    irisclient.resp(n,s,l,c,filename=respf)
                except Exception,msg:
                    sys.stderr.write('Error retrieving response information for channel %s: "%s"\n' % (channel,str(msg)))
                    continue
                trace.stats['lat'] = slat
                trace.stats['lon'] = slon
                trace.stats['height'] = sheight
                tf.close()
                if c.startswith('H'):
                    units = 'ACC'
                else:
                    units = 'VEL'
                seedresp = {'filename': respf,  # RESP filename
                             # Units to return response in ('DIS', 'VEL' or ACC)
                             'units': units
                             }

                #apply the calibration
                try:
                    trace.simulate(paz_remove=None,seedresp=seedresp) #now in m/s^2 or m/s
                except Exception,msg:
                    sys.stderr.write('Error calibrating channel %s: "%s"\n' % (channel,str(msg)))
                    continue

                #save as a Python pickle file since that preserves the lat/lon/height data
                pclfilename = os.path.join(outfolder,'%s.pickle' % (channel))
                pclfile = open(pclfilename,'wb')
                pickle.dump(st,pclfile)
                pclfile.close()
                datafiles.append(pclfilename)

        return datafiles

def readiris(seedfile): #trivial, since we saved as a Python pickle
    return read(seedfile)[0] #return the trace from the stream object that gets created

if __name__ == '__main__':
    ifetch = IrisBroadFetcher()
    dfiles = ifetch.fetch(35.532,-96.765,datetime.datetime(2011,11,06,03,53,10),None,None,'/Users/mhearne/tmp/iris')
        

    
