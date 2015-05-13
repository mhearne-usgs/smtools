#!/usr/bin/env python

#stdlib
from datetime import datetime,timedelta
import re
import sys
import os.path
import tarfile
import ftplib
import urlparse
import base64
from collections import OrderedDict
import urllib2
import urllib

#local
from fetcher import StrongMotionFetcher,StrongMotionFetcherException
from trace2xml import trace2xml
import util

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
import numpy as np
import matplotlib.pyplot as plt

TIMEFMT = '%Y/%m/%d %H:%M:%S'
DATEPAT = '[0-9]{4}/[0-9]{2}/[0-9]{2}-[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{2}'
DATEFMT = '%Y/%m/%d-%H:%M:%S.%f'
KNET_TRIGGER_DELAY = 15.0 #a delay in the KNet data logger - subtract this from "record time"
JPTIMEOFF = 9 * 3600 #number of seconds offset from GMT for Japan Standard time
FTPBASE = 'ftp://www.k-net.bosai.go.jp/knet/alldata/[YEAR]/[MONTH]'

#it is for some reason important that the CGI parameters for the combined knet/kiknet page
#be in a particular order.
CGIPARAMS = OrderedDict()
CGIPARAMS['formattype'] = 'A'
CGIPARAMS['eqidlist'] = ''
CGIPARAMS['datanames'] = ''
CGIPARAMS['alldata'] = None
CGIPARAMS['datakind'] = 'all'

KIKNETURL = 'http://www.kyoshin.bosai.go.jp/cgi-bin/kyoshin/quick/list_eqid_en.cgi?1+YEAR+QUARTER'
CGI = 'http://www.kyoshin.bosai.go.jp/cgi-bin/kyoshin/auth/makearc?%s'

class KNETFetcher(StrongMotionFetcher):
    """
    A class to handle retrieving strong motion data from the Japanese K-NET network.
    """
    def __init__(self,user,password):
        """
        Constructor
        @param user: Valid K-NET user name.
        @param password: Valid K-NET password.
        """
        self.user = user
        self.password = password

    def fetch(self,lat,lon,etime,radius,timewindow,outfolder):
        """
        Retrieve all strong motion data record files associated with an event.
        @param lat: Latitude associated with event
        @param lon: Longitude associated with event
        @param etime: UTC time of event
        @param radius: Distance window (km) within which to search for events on K-NET FTP site.
        @param timewindow: Time window (sec) within which to search for events on K-NET FTP site.
        @param outfolder: Folder where retrieved strong motion ASCII data files should be written.
        @return: List of strong motion ASCII data files.
        """
        jptime = etime + timedelta(seconds=JPTIMEOFF)
        tarfile = self.fetchKNet(self.user,self.password,jptime,timewindow)
        #tarfile = self.fetchKNetAndKikNet(self.user,self.password,jptime,timewindow)
        if tarfile is None:
            raise StrongMotionFetcherException('No K-NET data was found within %i seconds of %s (JST).  Returning.' % (timewindow,jptime))
        #datafiles = self.extractDataFiles(tarfile,outfolder)
        datafiles = self.extractAllDataFiles(tarfile,outfolder)
        os.remove(tarfile)
        return datafiles

    def extractAllDataFiles(self,tarfilename,tarfolder):
        """
        Unpack data files from tar file retrieved from K-NET and KikNet.
        """
        #tar file should contain three gzipped files:
        #eventid.knt.tar.gz - KNet data
        #eventid.kik.tar.gz - KikNet data
        #eventid.all.img.tar.gz - Plots, we don't care about these
        knetfolder = os.path.join(tarfolder,'knet')
        kikfolder = os.path.join(tarfolder,'kiknet')
        tarball = tarfile.open(name=tarfilename,mode='r')
        fnames = tarball.getnames()
        datafiles = []
        for fname in fnames:
            if fname.find('knt') > -1:
                outfolder = knetfolder
            if fname.find('kik') > -1:
                outfolder = kikfolder
            tarball.extract(fname,outfolder)
            tarfile2 = os.path.join(outfolder,fname)
            tarball2 = tarfile.open(name=tarfile2,mode='r:gz')
            tnames = tarball2.getnames()
            for tname in tnames:
                if tname.endswith('.gz'):
                    continue
                tarball2.extract(tname,path=outfolder)
                datafiles.append(os.path.abspath(os.path.join(outfolder,tname)))
            tarball2.close()
                
        tarball.close()
        return datafiles
    
    def extractDataFiles(self,tarfilename,tarfolder):
        """
        Unpack data files from tar file retrieved from K-NET.
        """
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

    def fetchKNetAndKikNet(self,user,password,jptime,timewindow):
        quarters = {1:1,2:1,3:1,
                    4:4,5:4,6:4,
                    7:7,8:7,9:7,
                    10:10,11:10,12:10}
        jpyear = str(jptime.year)
        jpquarter = str(quarters[jptime.month])
        url = KIKNETURL.replace('YEAR',jpyear)
        url = url.replace('QUARTER',jpquarter)
        fh = urllib2.urlopen(url)
        data = fh.read()
        fh.close()
        sidx = data.find('<SELECT NAME="eqidlist"')
        eidx = data.find('</SELECT>',sidx)+len('</SELECT>')
        newdata = data[sidx:eidx]
        lines = newdata.split('\n')
        localfile = None
        for line in lines[1:-1]:
            value = re.search('"(.*?)"',line).group().strip('"')
            datestr = re.search(DATEPAT,line).group()
            dtime = datetime.strptime(datestr,DATEFMT)
            if dtime > jptime:
                dt = dtime - jptime
            else:
                dt = jptime - dtime
            nsecs = dt.days*86400 + dt.seconds
            if nsecs > timewindow:
                continue
            cdict = CGIPARAMS.copy()
            cdict['eqidlist'] = value
            cdict['datanames'] = value.split(',')[0].strip()
            cparams = urllib.urlencode(cdict)
            #something strange and important about the placement and format of the "alldata" parameter
            cparams = cparams.replace('&alldata=None','%3Balldata')
            requesturl = CGI % cparams
            req = urllib2.Request(requesturl)
            base64string = base64.encodestring('%s:%s' % (user, password))[:-1]
            req.add_header("Authorization", "Basic %s" % base64string)
            handle = urllib2.urlopen(req)
            data = handle.read()
            handle.close()
            localfile = os.path.join(os.getcwd(),dtime.strftime('%Y%m%d%H%M%S')+'.tar')
            f = open(localfile,'wb')
            f.write(data)
            f.close()
            break
        return localfile
                
                                         
    
    def fetchKNet(self,user,password,jptime,timewindow):
        """
        Retrieve the tar file from the K-NET FTP site associated with a given time/timewindow.
        """
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
            kiknetcomps = {'1':'NS1','2':'EW1','3':'UD1',
                           '4':'NS2','5':'EW2','6':'UD2'}
            if channel.strip() in kiknetcomps.keys(): #kiknet directions are 1-6
                channel = kiknetcomps[channel.strip()]
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
        hdrdict['units'] = 'acc' #this will be in all of the headers I read
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
    hdrdict['network'] = 'NIED'
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
    username = sys.argv[1]
    password = sys.argv[2]
    etimestr = sys.argv[3]
    etime = datetime.strptime(etimestr,'%Y-%m-%dT%H:%M:%S')
    knet = KNETFetcher(username,password)
    datafiles = knet.fetch(34.1,-119.1,etime,radius=100,timewindow=120,outfolder=os.getcwd())
    
    
    
    
