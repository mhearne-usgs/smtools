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

#Kate's IRIS data fetcher code
from reviewData import reviewData

#local imports
from fetcher import StrongMotionFetcher,StrongMotionFetcherException
from trace2xml import trace2xml

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
        st = reviewData.getepidata(lat, lon, etimestr, tstart=-3,
                                   tend=+timewindow, minradiuskm=0., maxradiuskm=radius,
                                   channels='strong motion', location='*', source='IRIS')
        seedfiles = []
        if st is not None:
            stacc,stvel = reviewData.getpeaks(st,pga=False,pgv=False,psa=False)
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

    
