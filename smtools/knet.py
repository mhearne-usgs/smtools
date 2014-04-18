#!/usr/bin/env python

#stdlib
from datetime import datetime
import re
import sys
import os.path
import tarfile
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

TIMEFMT = '%Y/%m/%d %H:%M:%S'
KNET_TRIGGER_DELAY = 15.0 #a delay in the KNet data logger - subtract this from "record time"
JPTIMEOFF = 9 * 3600 #number of seconds offset from GMT for Japan Standard time

def fetchKNet(user,password,jptime,timewindow):
    url = FTPBASE.replace('[USER]',user)
    url = url.replace('[PASSWORD]',password)
    yearstr = '%4i' % jptime.year
    monthstr = '%02i' % jptime.month
    url = url.replace('[YEAR]',yearstr)
    url = url.replace('[MONTH]',monthstr)
    urlparts = urlparse.urlparse(url)
    ftp = ftplib.FTP(urlparts.netloc)
    ftp.login(user,password)
    dirparts = urlparts.path.strip('/').split('/')
    for d in dirparts:
        try:
            ftp.cwd(d)
        except ftplib.error_perm,msg:
            raise Exception,msg
    ftpfiles = ftp.nlst()
    localfile = None
    for ftpfile in ftpfiles:
        if not ftpfile.endswith('.gz'):
            continue
        year = int(ftpfile[0:4])
        month = int(ftpfile[4:6])
        day = int(ftpfile[6:8])
        hour = int(ftpfile[8:10])
        minute = int(ftpfile[10:12])
        second = int(ftpfile[12:14])
        tmptime = datetime(year,month,day,hour,minute,second)
        if tmptime > jptime:
            dt = tmptime - jptime
        else:
            dt = jptime - tmptime
        nsecs = dt.days*86400 + dt.seconds
        if nsecs > timewindow:
            continue

        localfile = os.path.join(os.getcwd(),ftpfile)
        f = open(localfile,'wb')
        ftp.retrbinary('RETR %s' % ftpfile,f.write)
        f.close()
        break
    ftp.quit()
    return localfile

def extractDataFiles(tarfilename,tarfolder):
    tarball = tarfile.open(name=tarfilename,mode='r:gz')
    fnames = tarball.getnames()
    datafiles = []
    for fname in fnames:
        if fname.endswith('.gz'):
            continue
        tarball.extract(fname,path=tarfolder)
        datafiles.append(os.path.abspath(os.path.join(tarfolder,fname)))
    tarball.close()
    return datafiles

def getDataFiles(args,config,outfolder,timewindow):
    #There are three ways to specify the time of the desired earthquake
    #By event id:
    if args.folder:
        tarfolder = args.folder
    else:
        tarfolder = os.getcwd()
    if args.eventID:
        eventfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID)
        eventxml = os.path.join(eventfolder,'input','event.xml')
        if not os.path.isfile(eventxml):
            print 'Could not find an event.xml file at %s.  Returning.' % eventxml
            sys.exit(1)
        
        if args.keep:
            tarfolder = os.path.join(eventfolder,'raw')
        else:
            tarfolder = os.getcwd()
            
        utctime = util.parseEvent(eventxml)
        jptime = utctime + timedelta(seconds=JPTIMEOFF)

    #By UTC time
    if args.UTCTime:
        jptime = args.UTCTime + timedelta(seconds=JPTIMEOFF)

    #There are two ways to specify username/password
    #By explicitly passing them in or by reading the config file
    if (args.user and not args.password) or (args.password and not args.user):
        print 'You must specify both user and password, or neither.  Returning.'
        sys.exit(1)
        
    if args.user:
        user = args.user
        password = args.password
    else:
        if config:
            user = config.get('KNET','user')
            password = config.get('KNET','password')
        else:
            print 'You did not specify user/password, and you do not have a config file.  Returning.'
            sys.exit(1)
            
    #we now should have the user,password,jptime, and output filename.  This should be enough to find the event on
    #the Japanese FTP site
    tarfile = fetchKNet(user,password,jptime,timewindow)
    if tarfile is None:
        print 'No K-NET data was found within %i seconds of %s (JST).  Returning.' % (args.timeWindow,jptime)
        sys.exit(1)

    datafiles = extractDataFiles(tarfile,tarfolder)
    return (tarfile,datafiles)

def readheader(hdrlines):
    """
    Read the header values of a KNet ASCII file into a dictionary.

    @param hdlines: List of the first lines of a KNet ASCII file, not including the "Memo." line.
    @return: Dictionary of values containing most of the elements expected in a Stats object.
    """
    hdrdict = {}
    for line in hdrlines:
        if line.startswith('Station Code'):
            parts = line.split()
            hdrdict['station'] = parts[2]
        if line.startswith('Station Lat'):
            parts = line.split()
            hdrdict['lat'] = float(parts[2])
        if line.startswith('Station Long'):
            parts = line.split()
            hdrdict['lon'] = float(parts[2])
        if line.startswith('Station Height'):
            parts = line.split()
            hdrdict['height'] = float(parts[2])
        if line.startswith('Record Time'):
            parts = line.split()
            datestr = parts[2]+' '+parts[3]
            hdrdict['starttime'] = UTCDateTime(datetime.strptime(datestr,TIMEFMT)) - KNET_TRIGGER_DELAY
        if line.startswith('Sampling Freq'):
            parts = line.split()
            freqstr = parts[2]
            m = re.search('[0-9]*',freqstr)
            freq = int(m.group())
            delta = 1.0/freq
            hdrdict['delta'] = delta
            hdrdict['sampling_rate'] = freq
        if line.startswith('Duration Time'):
            parts = line.split()
            duration = float(parts[2])
            hdrdict['duration'] = duration
        if line.startswith('Dir.'):
            parts = line.split()
            channel = parts[1].replace('-','')
            hdrdict['channel'] = channel
        if line.startswith('Scale Factor'):
            parts = line.split()
            eqn = parts[2]
            num,denom = eqn.split('/')
            num = float(re.search('[0-9]*',num).group())
            denom = float(denom)
            hdrdict['calib'] = num/denom
        if line.startswith('Max. Acc'):
            parts = line.split()
            acc = float(parts[3])
            hdrdict['accmax'] = acc
    return hdrdict

def readknet(knetfilename):
    """
    Read a KNet ASCII file, and return an ObsPy Trace object, plus a dictionary of header values.

    @param knetfilename: String path to valid KNet ASCII file, as described here: http://www.kyoshin.bosai.go.jp/kyoshin/man/knetform_en.html
    @return: ObsPy Trace object, and a dictionary of some of the header values found in the input file.
    """
    data = []
    hdrdict = {}
    f = open(knetfilename,'rt')
    dataOn = False
    headerlines = []
    for line in f.readlines():
        if line.startswith('Memo'):
            hdrdict = readheader(headerlines)
            dataOn = True
            continue
        if not dataOn:
            headerlines.append(line)
            continue
        if dataOn:
            parts = line.strip().split()
            mdata = [float(p) for p in parts]
            data = data + mdata
    f.close()

    #fill in the values usually expected in Stats as best we can
    hdrdict['npts'] = len(data)
    elapsed = float(hdrdict['npts'])/float(hdrdict['sampling_rate'])
    hdrdict['endtime'] = hdrdict['starttime'] + elapsed
    hdrdict['network'] = 'JP'
    hdrdict['location'] = ''

    #The Stats constructor appears to modify the fields in the input dictionary - let's save
    #a copy
    header = hdrdict.copy()
    
    data = np.array(data)
    stats = Stats(hdrdict)
    trace = Trace(data,header=stats)

    #apply the calibration and convert to m/s^2
    trace.data = trace.data * trace.stats['calib'] * 0.01 #convert to m/s^2
    
    return (trace,header)
    
if __name__ == '__main__':
    knetfile = sys.argv[1]
    trace,header = readknet(knetfile)
    print trace.data.max()
    trace.detrend('demean')
    trace.plot()
    plt.savefig('knet.png')
    print trace.data.max()
    print trace.stats['calib']
    print trace.data.max() * trace.stats['calib']
    stationfile,plotfiles = trace2xml([trace],None,os.getcwd(),doPlot=True)
    
    
    
