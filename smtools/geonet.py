#!/usr/bin/env python

import warnings
warnings.simplefilter("ignore", DeprecationWarning)
import numpy.oldnumeric

#stdlib imports
from datetime import datetime
import sys
import os.path
import urlparse
import ftplib

#local
from trace2xml import trace2xml
import util

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
import numpy as np
import matplotlib.pyplot as plt

def getDataFiles(args,config,outfolder,timewindow):
    GEOBASE = 'ftp://ftp.geonet.org.nz/strong/processed/Proc/[YEAR]/[MONTH]/'
    if args.eventID:
        eventfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID)
        eventxml = os.path.join(eventfolder,'input','event.xml')
        if not os.path.isfile(eventxml):
            print 'Could not find an event.xml file at %s.  Returning.' % eventxml
            sys.exit(1)
        utctime = util.parseEvent(eventxml)
    #By UTC time
    if args.UTCTime:
        utctime = args.UTCTime

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
        
    eventlist = ftp.nlst()
    datafiles = []
    for fname in eventlist:
        etime = datetime.strptime(fname,'%Y-%m-%d_%H%M%S')
        if etime > utctime:
            dt = etime - utctime
        else:
            dt = utctime - etime
        nsecs = dt.days*86400 + dt.seconds
        if nsecs > timewindow:
            continue
        try:
            ftp.cwd(fname)
        except:
            pass
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
    

def readgeonet(geonetfile):
    f = open(geonetfile,'rt')
    hdrlines = []
    for i in range(0,26):
        hdrlines.append(f.readline())

    hdrdict = readheader(hdrlines)
    numlines = hdrdict['npts']/10
    data = []
    for i in range(0,numlines):
        line = f.readline()
        parts = line.strip().split()
        mdata = [float(p) for p in parts]
        data = data + mdata
    f.close()
    
    data = np.array(data)
    header = hdrdict.copy()
    stats = Stats(hdrdict)
    trace = Trace(data,header=stats)

    #apply the calibration and convert from mm/s^2 to m/s^2
    trace.data = trace.data * trace.stats['calib'] * 0.001 #convert to m/s^2
    
    return (trace,header)

if __name__ == '__main__':
    geonetfile = sys.argv[1]
    trace,header = readgeonet(geonetfile)
    print trace.data.max()
    trace.detrend('demean')
    trace.plot()
    plt.savefig('geonet.png')
    print trace.data.max()
    print trace.stats['calib']
    print trace.data.max() * trace.stats['calib']
    stationfile,plotfiles,tag = trace2xml([trace],None,os.getcwd(),doPlot=True)
