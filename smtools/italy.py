#!/usr/bin/env python

import warnings
warnings.simplefilter("ignore", DeprecationWarning)
#import numpy.oldnumeric

#stdlib imports
from datetime import datetime,timedelta
import sys
import os.path
import urllib.parse
import ftplib
import urllib.request, urllib.error, urllib.parse
from xml.dom import minidom

#local
from .fetcher import StrongMotionFetcher,StrongMotionFetcherException
from .trace2xml import trace2xml
from . import util

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
from obspy.core.util.geodetics import gps2DistAzimuth
import numpy as np
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

HEADERS = {'STATION_CODE':'station',
           'STREAM':'channel',
           'LOCATION':'location',
           'NDATA':'npts',
           'DATA_TIME_FIRST_SAMPLE_YYYYMMDD_HHMMSS':'starttime',
           'SAMPLING_INTERVAL_S':'delta',
           'STATION_LATITUDE_DEGREE':'lat',
           'STATION_LONGITUDE_DEGREE':'lon',
           'STATION_ELEVATION':'height',
           'DURATION_S':'duration',
           'NETWORK':'network'}

TIMEFMT = '%Y%m%d_%H%M%S.%f'

URL = 'http://itaca.mi.ingv.it/ItacaNet/CadmoDriver?_action_prepare_find_div=1&_page=ACC_Events_Stations_Waveform_progressive&_rock=INVALID&_state=find_progressive_div&_tabber=1&_token=NULLNULLNULLNULL&_startvalue_event_time=STARTTIME&_stopvalue_event_time=STOPTIME'

def fetchItaly(starttime,endtime):
    url = URL.replace('STARTTIME',starttime.strftime('%Y-%m-%d'))
    url = url.replace('STOPTIME',endtime.strftime('%Y-%m-%d'))
    fh = urllib.request.urlopen(url)
    data = fh.read()
    fh.close()
    startidx = data.find('<table class="CADMOMAINTABLE">')
    endidx = data.find('<!-- end of CADMOMAINTABLE -->')
    newdata = data[startidx:endidx]
    soup = BeautifulSoup(newdata)
    rows = soup.findAll('tr')
    for row in rows[1:]:
        cell = row.findAll('td')[0]
        anchor = cell.findAll('a')[0]
        eventid = anchor['id']
        #2009-04-05 20:20:53
        etime = datetime.strptime(anchor.string,'%Y-%m-%d %H:%M:%S')
        print(eventid,str(etime))

def readitaly(datafile):
    f = open(datafile,'rt')
    #header needs: station,channel,location,npts,starttime,sampling_rate,delta,calib,lat,lon,height,duration,endtime,maxacc,network
    data = []
    hdrdict = {}
    for line in f.readlines():
        if not len(line.strip()):
            continue
        if not line.find(':') > -1:
            data.append(float(line.strip()))
            continue

        key,value = line.split(':')
        key = key.strip()
        value = value.strip()
        if key not in list(HEADERS.keys()):
            continue
        hdrkey = HEADERS[key]
        if hdrkey == 'starttime':
            value = UTCDateTime(datetime.datetime.strptime(value,TIMEFMT))
        elif hdrkey not in ['station','channel','location','network']:
            value = float(value)
        hdrdict[hdrkey] = value
    f.close()
    hdrdict['sampling_rate'] = 1/hdrdict['delta']
    hdrdict['endtime'] = hdrdict['starttime'] + hdrdict['duration']
    hdrdict['npts'] = int(hdrdict['npts'])
    hdrdict['calib'] = 1.0
    hdrdict['units'] = 'acc'
    data = np.array(data)
    header = hdrdict.copy()
    stats = Stats(hdrdict)
    trace = Trace(data,header=stats)
    #apply the calibration and convert from mm/s^2 to m/s^2
    trace.data = trace.data * trace.stats['calib'] * 0.01 #convert to m/s^2
    return trace

if __name__ == '__main__':
    # filename = sys.argv[1]
    # trace = readitaly(filename)
    # trace.plot()
    # plt.savefig('tmpitaly.png')
    starttime = datetime(2009,4,5)
    stoptime = datetime(2009,4,6)
    fetchItaly(starttime,stoptime)
    
