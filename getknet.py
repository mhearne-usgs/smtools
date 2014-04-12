#!/usr/bin/env python

#stdlib
import warnings
# with warnings.catch_warnings():
#     warnings.filterwarnings("ignore",category=ModuleDeprecationWarning)

import ftplib
import urlparse
import sys
import tarfile
from datetime import datetime,timedelta
from ConfigParser import ConfigParser,RawConfigParser
import os.path
import argparse

#import local
from smtools.knet import readknet
from smtools.trace2xml import trace2xml

#URLBASE = 'ftp://[USER]:[PASSWORD]@www.k-net.bosai.go.jp/knet/alldata/[YEAR]/[MONTH]/[REMOTEID].knt.tar.gz'
FTPBASE = 'ftp://www.k-net.bosai.go.jp/knet/alldata/[YEAR]/[MONTH]'
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
JPTIMEOFF = 9 * 3600 #number of seconds offset from GMT for Japan Standard time
TIMEWINDOW = 10 #number of seconds within which to search for matching event on knet site

def extractDataFiles(tarfilename):
    tarball = tarfile.open(name=tarfilename,mode='r:gz')
    fnames = tarball.getnames()
    datafiles = []
    for fname in fnames:
        if fname.endswith('.gz'):
            continue
        tarball.extract(fname)
        datafiles.append(os.path.abspath(os.path.join(os.getcwd(),fname)))
    tarball.close()
    return datafiles

def fetchKNet(user,password,jptime):
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
        if nsecs > TIMEWINDOW:
            continue

        localfile = os.path.join(os.getcwd(),ftpfile)
        f = open(localfile,'wb')
        ftp.retrbinary('RETR %s' % ftpfile,f.write)
        f.close()
        break
    ftp.quit()
    return localfile

def maketime(timestring):
    outtime = None
    try:
        outtime = datetime.strptime(timestring,TIMEFMT)
    except:
        try:
            outtime = datetime.strptime(timestring,DATEFMT)
        except:
            raise Exception,'Could not parse time or date from %s' % timestring
    return outtime


def doConfig():
    shakehome = raw_input('Please specify the root folder where ShakeMap is installed: ')
    if not os.path.isdir(shakehome):
        print '%s is not a valid path.  Returning.' % shakehome
    user = raw_input('Please specify K-NET user name: ')
    password = raw_input('Please specify K-NET password: ')
    config = RawConfigParser()
    config.add_section('KNET')
    config.add_section('SHAKEMAP')
    config.set('KNET','user',user)
    config.set('KNET','password',password)
    config.set('SHAKEMAP','shakehome',shakehome)
    homedir = os.path.expanduser('~')
    configfolder = os.path.join(homedir,'.smtools')
    configfile = os.path.join(configfolder,'config.ini')
    if not os.path.isdir(configfolder):
        os.makedirs(configfolder)
    with open(configfile, 'wb') as configfile:
        config.write(configfile)
    
    

def main(args,config):
    if args.doConfig:
        doConfig()
        sys.exit(0)
    if args.eventID and config is None:
        print 'To specify event ID, you must have configured the ShakeHome parameter in the config file.'
        print 'Re-run with -config.  Returning.'
        sys.exit(1)
    #There are three ways to specify the time of the desired earthquake
    #By event id:
    if args.eventID:
        eventxml = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'input','event.xml')
        if not os.path.isfile(eventxml):
            print 'Could not find an event.xml file at %s.  Returning.' % eventxml
            sys.exit(1)
        
        utctime = parseEvent(eventxml)
        jptime = utctime + timedelta(seconds=JPTIMEOFF)
        if not args.folder:
            outfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'input')
        else:
            outfolder = args.folder
    else:
        if args.folder:
            outfolder = args.folder
        else:
            outfolder = os.getcwd()

    #By UTC time
    if args.UTCTime:
        jptime = args.UTCTime + timedelta(seconds=JPTIMEOFF)

    #By Japan standard time
    if args.JPTime:
        jptime = args.JPTime
        utctime = jptime - timedelta(seconds=JPTIMEOFF)

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
    tarfile = fetchKNet(user,password,jptime)
    if tarfile is None:
        print 'No K-NET data was found within %i seconds of %s (JST).  Returning.' % (TIMEWINDOW,jptime)
        sys.exit(1)

    datafiles = extractDataFiles(tarfile)
    traces = []
    for dfile in datafiles:
        trace,header = readknet(dfile)
        traces.append(trace)

    stationfile = trace2xml(traces,None,outfolder,doPlot=args.doPlot)
    print 'Wrote %i channels to data file %s' % (len(traces),stationfile)
    if not args.keeptar:
        os.remove(tarfile)
        for dfile in datafiles:
            os.remove(dfile)
    sys.exit(0)
    
    

if __name__ == '__main__':
    #look for config file
    configfile = os.path.join(os.path.expanduser('~'),'.smtools','config.ini')
    config = None
    if os.path.isfile(configfile):
        config = ConfigParser()
        config.readfp(open(configfile))
    desc = '''Download and process K-NET strong motion data into peak ground motion values, and output in an
        XML format.
        Usage:
        
        '''
    parser = argparse.ArgumentParser(description='Download Japanese K-NET strong motion data for a selected event.')
    parser.add_argument('-c','-config',dest='doConfig',action='store_true',default=False,
                        help='Create config file for future use')
    parser.add_argument('-e','-event',dest='eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('-t','-utctime',dest='UTCTime',help='Specify UTC Time for event.',type=maketime)
    parser.add_argument('-j','-jptime',dest='JPTime',help='Specify Japanese Standard Time for event.',type=maketime)
    parser.add_argument('-f','-folder',dest='folder',help='Specify output station folder destination (defaults to event input folder or current working directory)',default=os.getcwd())
    parser.add_argument('-u','-user',dest='user',help='Specify user (defaults to value in config)')
    parser.add_argument('-p','-password',dest='password',help='Specify password (defaults to value in config)')
    parser.add_argument('-k','-keep',dest='keepTar',action='store_true',default=False,
                        help='Retain tarfile and extracted ASCII data files')
    parser.add_argument('-o','-plot',dest='doPlot',action='store_true',default=False,
                        help='Make QA plots')
    pargs = parser.parse_args()
    main(pargs,config)    
    

    
