#!/usr/bin/env python

import warnings
warnings.simplefilter("ignore", DeprecationWarning)
import numpy.oldnumeric

#stdlib imports
from datetime import datetime,timedelta
import sys
import os.path
import urlparse
import ftplib
import urllib2

#local
from trace2xml import trace2xml
import util

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
from obspy.core.util.geodetics import gps2DistAzimuth
import numpy as np
import matplotlib.pyplot as plt

CATBASE = 'http://quakesearch.geonet.org.nz/services/1.0.0/csv?startdate=[START]&enddate=[END]'
GEOBASE = 'ftp://ftp.geonet.org.nz/strong/processed/Proc/[YEAR]/[MONTH]/'
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
NZTIMEDELTA = 2 #number of seconds allowed between GeoNet catalog time and event timestamp on FTP site
NZCATWINDOW = 5*60 #number of seconds to search around in GeoNet EQ catalog

def checkCatalog(time,lat,lon,timewindow,distwindow):
    stime = time - timedelta(seconds=NZCATWINDOW)
    etime = time + timedelta(seconds=NZCATWINDOW)
    url = CATBASE.replace('[START]',stime.strftime(TIMEFMT))
    url = url.replace('[END]',etime.strftime(TIMEFMT))
    try:
        fh = urllib2.urlopen(url)
        data = fh.read()
        fh.close()
        lines = data.split('\n')
        for line in lines[1:]:
            #time is column 2, longitude is column 4, latitude is column 5
            parts = line.split(',')
            eid = parts[0]
            etime = datetime.strptime(parts[2][0:19],TIMEFMT)
            elat = float(parts[5])
            elon = float(parts[4])
            if etime > time:
                dt = etime - time
            else:
                dt = time - etime
            nsecs = dt.days*86400 + dt.seconds
            dd,az1,az2 = gps2DistAzimuth(lat,lon,elat,elon)
            dd = dd/1000.0
            if nsecs <= timewindow and dd < distwindow:
                return (eid,etime)
    except Exception,msg:
        raise Exception,'Could not access the GeoNet website - got error "%s"' % str(msg)
    return (None,None)

def getDataFiles(config,outfolder,timewindow,distwindow,eventid=None,eventtime=None,lat=None,lon=None):
    if eventid:
        eventfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',eventid)
        eventxml = os.path.join(eventfolder,'input','event.xml')
        if not os.path.isfile(eventxml):
            print 'Could not find an event.xml file at %s.  Returning.' % eventxml
            sys.exit(1)
        utctime,lat,lon = util.parseEvent(eventxml)
    #By UTC time
    if eventtime:
        utctime = eventtime

    #get the most likely event time and ID for the event we input
    eid,gtime = checkCatalog(utctime,lat,lon,timewindow,distwindow)
    if eid is None:
        print 'Could not find this event in the GeoNet earthquake catalog.  Returning.'
        sys.exit(1)
    print 'This event is most likely the NZ event %s.' % eid
        
    #set up the ftp url for this day and month
    #[MONTH] should be in the format mm_Mon (04_Apr, 05_May, etc.)
    neturl = GEOBASE.replace('[YEAR]',str(utctime.year))
    monthstr = utctime.strftime('%m_%b')
    neturl = neturl.replace('[MONTH]',monthstr)
    urlparts = urlparse.urlparse(neturl)
    ftp = ftplib.FTP(urlparts.netloc)
    ftp.login() #anonymous
    dirparts = urlparts.path.strip('/').split('/')
    for d in dirparts:
        try:
            ftp.cwd(d)
        except ftplib.error_perm,msg:
            raise Exception,msg

    #cd to the desired output folder
    os.chdir(outfolder)
    datafiles = []

    #create the event folder name from the time we got above
    fname = gtime.strftime('%Y-%m-%d_%H%M%S')

    try:
        ftp.cwd(fname)
    except:
        print 'Could not find an FTP data folder called "%s". Returning.' % (urlparse.urljoin(neturl,fname))
        sys.exit(1)
        
    volumes = []
    dirlist = ftp.nlst()
    for volume in dirlist:
        if volume.startswith('Vol'):
            ftp.cwd(volume)
            ftp.cwd('data')
            flist = ftp.nlst()
            for ftpfile in flist:
                if not ftpfile.endswith('V1A'):
                    continue
                localfile = os.path.join(os.getcwd(),ftpfile)
                if localfile in datafiles:
                    continue
                datafiles.append(localfile)
                f = open(localfile,'wb')
                sys.stderr.write('Retrieving remote file %s...\n' % ftpfile)
                ftp.retrbinary('RETR %s' % ftpfile,f.write)
                f.close()
            ftp.cwd('..')
            ftp.cwd('..')

    ftp.quit()
    return datafiles

def readheader(lines):
    hdrdict = {}
    #input list of 26 lines of header
    #station and channel
    line = lines[5]
    parts = line.strip().split()
    fname = parts[1]
    fparts = fname.split('_')
    hdrdict['station'] = fparts[-2]+'_'+fparts[-1]
    hdrdict['channel'] = ''
    #location string
    line = lines[6]
    hdrdict['location'] = ''
    #event origin, buffer start year/month
    line = lines[16]
    parts = line.strip().split()
    bufyear = int(parts[8])
    bufmonth = int(parts[9])
    #epicentral location, buffer start day/hour
    line = lines[17]
    parts = line.strip().split()
    bufday = int(parts[8])
    bufhour = int(parts[9])
    #numpoints, buffer start min/sec
    line = lines[19]
    parts = line.strip().split()
    hdrdict['npts'] = int(parts[0])
    bufmin = int(parts[8])
    millisec = int(parts[9])
    bufsec = millisec/1000
    bufmicrosec = int(np.round(millisec/1000.0 - bufsec))
    hdrdict['starttime'] = UTCDateTime(datetime(bufyear,bufmonth,bufday,bufhour,bufmin,bufsec,bufmicrosec))
    #part C
    #frequency, calibration value and some other stuff we don't care about
    line = lines[20]
    parts = line.strip().split()
    hdrdict['sampling_rate'] = float(parts[0])
    hdrdict['delta'] = 1.0/hdrdict['sampling_rate']
    hdrdict['calib'] = float(parts[7])
    #site location info, this time in dd
    line = lines[21]
    parts = line.strip().split()
    hdrdict['lat'] = float(parts[0]) * -1
    hdrdict['lon'] = float(parts[1])
    hdrdict['height'] = 0.0
    #duration
    line = lines[22]
    parts = line.strip().split()
    hdrdict['duration'] = float(parts[0])
    hdrdict['endtime'] = hdrdict['starttime'] + hdrdict['duration']
    #max acceleration - good for sanity check
    line = lines[23]
    parts = line.strip().split()
    hdrdict['maxacc'] = float(parts[0])
    hdrdict['network'] = 'NZ'
    return hdrdict
    

def readheaderlines(f):
    hdrlines = []
    for i in range(0,26):
        hdrlines.append(f.readline())
    return hdrlines

def readgeonet(geonetfile):
    f = open(geonetfile,'rt')
    tracelist = []
    headerlist = []
    hdrlines = readheaderlines(f)
    while len(hdrlines[-1]):
        hdrdict = readheader(hdrlines)
        numlines = hdrdict['npts']/10
        data = []
        for i in range(0,numlines):
            line = f.readline()
            parts = line.strip().split()
            mdata = [float(p) for p in parts]
            data = data + mdata
        data = np.array(data)
        header = hdrdict.copy()
        stats = Stats(hdrdict)
        trace = Trace(data,header=stats)
        #apply the calibration and convert from mm/s^2 to m/s^2
        trace.data = trace.data * trace.stats['calib'] * 0.001 #convert to m/s^2
        tracelist.append(trace.copy())
        headerlist.append(header.copy())
        hdrlines = readheaderlines(f)

    f.close()
    return (tracelist,headerlist)

if __name__ == '__main__':
    geonetfile = sys.argv[1]
    traces,headers = readgeonet(geonetfile)
    print trace.data.max()
    trace.detrend('demean')
    trace.plot()
    plt.savefig('geonet.png')
    print traces[0].data.max()
    print traces[0].stats['calib']
    print traces[0].data.max() * trace.stats['calib']
    stationfile,plotfiles,tag = trace2xml(traces,None,os.getcwd(),doPlot=True)
