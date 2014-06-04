#!/usr/bin/env python

#stdlib
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
import numpy.oldnumeric

import sys
import tarfile
from datetime import datetime,timedelta
from ConfigParser import ConfigParser,RawConfigParser
import os.path
import argparse
import glob
import re
import collections

#import local
from smtools import knet,geonet,turkey,util
from smtools.trace2xml import trace2xml

#constants
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
TIMEWINDOW = 60 #number of seconds within which to search for matching event on knet/geonet site
DISTWINDOW = 50 #number of seconds within which to search for matching event on knet/geonet site

class ValidateParams(argparse.Action):
    def __call__(self, parser, args, values, option_string=None):
        # print '{n} {v} {o}'.format(n=args, v=values, o=option_string)
        etimestr, latstr,lonstr = values
        try:
            etime = maketime(etimestr)
        except Exception,instance:
            raise ValueError('Invalid time string %s' % etimestr)
        try:
            lat = float(latstr)
        except:
            raise ValueError('Invalid latitude value %s' % latstr)
        try:
            lon = float(lonstr)
        except:
            raise ValueError('Invalid longitude value %s' % lonstr)
        Params = collections.namedtuple('Params', ['time','lat','lon'])
        setattr(args, self.dest, Params(etime,lat,lon))

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

def getOutFolders(args,config):
    #There are three ways to specify the time of the desired earthquake
    #By event id:
    if args.eventID:
        if not args.folder:
            outfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'input')
            rawfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'raw')
        else:
            outfolder = args.folder
            rawfolder = args.folder
    else:
        if args.folder:
            outfolder = args.folder
            rawfolder = args.folder
        else:
            outfolder = os.getcwd()
            rawfolder = outfolder
    return (outfolder,rawfolder)

def printTag(tag):
    for stationtag in tag.getChildren('station'):
        atts = stationtag.attributes
        print '%s - %s %.4f,%.4f' % (atts['code'],atts['name'],atts['lat'],atts['lon'])
        comptag = stationtag.getChildren('comp')[0]
        veltag = comptag.getChildren('vel')[0]
        acctag = comptag.getChildren('acc')[0]
        psa03tag = comptag.getChildren('psa03')[0]
        psa10tag = comptag.getChildren('psa10')[0]
        psa30tag = comptag.getChildren('psa30')[0]
        print '\tPeak Acceleration: %f' % (acctag.attributes['value'])
        print '\tPeak Velocity: %f' % (veltag.attributes['value'])
        print '\tPSA 0.3: %f' % (psa03tag.attributes['value'])
        print '\tPSA 1.0: %f' % (psa10tag.attributes['value'])
        print '\tPSA 3.0: %f' % (psa30tag.attributes['value'])
        print
        
def main(args,config):
    if args.doConfig:
        doConfig()
        sys.exit(0)
    if args.eventID and config is None:
        print 'To specify event ID, you must have configured the ShakeHome parameter in the config file.'
        print 'Re-run with -config.  Returning.'
        sys.exit(1)

    #Get the output folder
    outfolder,rawfolder = getOutFolders(args,config)
    if not os.path.isdir(rawfolder):
        os.makedirs(rawfolder)

    if args.eventID and (hasattr(args,'time') or hasattr(args,'lat') or hasattr(args,'lon')):
        print 'Supply EITHER eventID OR time,lat,lon - not both'
        sys.exit(1)

    if (args.user and not args.password) or (args.password and not args.user):
        print 'You must supply both KNET username AND password'
        sys.exit(1)
        
    if args.eventID:
        eventfile = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'input','event.xml')
        etime,lat,lon = util.parseEvent(eventfile)

    if args.Params:
        etime = args.Params.time
        lat = args.Params.lat
        lon = args.Params.lon
        
    datafiles = []
    if not args.inputFolder:
        if args.source == 'knet':
            if args.user:
                user = config.get('KNET','user')
                password = config.get('KNET','password')
            sys.stderr.write('Fetching strong motion data from NIED...\n')
            fetcher = knet.KNETFetcher(user,password)
        elif args.source == 'geonet':
            sys.stderr.write('Fetching strong motion data from GeoNet...\n')
            fetcher = geonet.GeonetFetcher()
        elif args.source == 'turkey':
            sys.stderr.write('Fetching strong motion data from Turkey...\n')
            fetcher = turkey.GeonetFetcher()
        else:
            print 'You must specify a source for the strong motion data.'
            sys.exit(1)
        datafiles = fetcher.fetch(lat,lon,etime,args.radius,args.timeWindow,rawfolder)
        sys.stderr.write('Retrieved %i files.\n' % len(datafiles))
    else: 
        if args.source == 'knet':
            datafiles1 = glob.glob(os.path.join(args.inputFolder,'*.NS'))
            datafiles2 = glob.glob(os.path.join(args.inputFolder,'*.EW'))
            datafiles3 = glob.glob(os.path.join(args.inputFolder,'*.UD'))
            datafiles = datafiles1+datafiles2+datafiles3
        elif args.source == 'geonet':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.V1A'))
        else: #turkey, for now
            datafiles1 = glob.glob(os.path.join(args.inputFolder,'*.txt'))
            datafiles = []
            for d in datafiles:
                dpath,dfile = os.path.split(d)
                if re.match('[0-9]{4}',dfile) is not None:
                    datafiles.append(d)
            
        
    
    traces = []
    for dfile in datafiles:
        if args.source == 'knet':
            trace,header = knet.readknet(dfile)
            traces.append(trace)
        elif args.source == 'geonet':
            tracelist,headers = geonet.readgeonet(dfile)
            traces = traces + tracelist
        elif args.source == 'turkey':
            tracelist,headers = turkey.readturkey(dfile)
            traces = traces + tracelist
        else:
            print 'Source %s is not supported' % (args.source)
            sys.exit(1)

    sys.stderr.write('Converting %i files to peak ground motion...\n' % len(datafiles))
    stationfile,plotfiles,tag = trace2xml(traces,None,outfolder,doPlot=args.doPlot)
    if args.debug:
        os.remove(stationfile)
        for pfile in plotfiles:
            os.remove(pfile)
        printTag(tag)
    
    #if the user specified an input folder, but did not specify to keep, keep anyway
    if args.nuke:
        for dfile in datafiles:
            os.remove(dfile)
    else:
        if not args.debug:
            sys.stderr.write('Wrote %i channels to data file %s\n' % (len(traces),stationfile))
    sys.exit(0)

if __name__ == '__main__':
    #look for config file
    configfile = os.path.join(os.path.expanduser('~'),'.smtools','config.ini')
    config = None
    if os.path.isfile(configfile):
        config = ConfigParser()
        config.readfp(open(configfile))
    desc = '''
        Download and process strong motion data from different sources
        (NZ GeoNet, JP K-NET, Turkey) into peak ground motion values,
        and output in an XML format suitable for inclusion in
        ShakeMap.
        
        Generic (non-ShakeMap) Usage:
        To configure the system for further use (you will be prompted for 
        KNET username/password, and ShakeMap home):
        getstrong.py -c
        To process data from a local folder (rather than downloading from a remote source):
        getstrong.py -i INPUTFOLDER -f OUTPUTFOLDER
        To process data from a local folder and print peak ground motions to the screen:
        getstrong.py -i INPUTFOLDER -d

        To retrieve data from K-NET with a user-supplied K-NET username/password:
        getstrong.py knet -f ~/tmp/knet -y 2014-05-04T20:18:24 34.862 139.312 -u fred -p SECRETPASSWD

        To retrieve data from GeoNet:
        getstrong.py geonet -f ~/tmp/knet -y 2014-01-20T02:52:44 40.660 175.814

        To retrieve data from Turkey:
        getstrong.py turkey -f ~/tmp/knet -y 2003-05-01T00:27:06 38.970 40.450

        ###############################################################
        For Shakemap Users:
        To download K-NET data for an event into it's input folder, while retaining the raw data:
        
        getstrong.py knet -e EVENTID
        
        To download K-NET data for an event into it's input folder, while deleting the raw data:
        
        getstrong.py knet -e EVENTID -n
        '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('source',help='Specify strong motion data source.',choices=['knet','geonet','turkey'])
    parser.add_argument('-c','-config',dest='doConfig',action='store_true',default=False,
                        help='Create config file for future use')
    parser.add_argument('-i','-inputfolder',dest='inputFolder',
                        help='process files from an input folder.')
    parser.add_argument('-d','-debug',dest='debug',action='store_true',default=False,
                        help='print peak ground motions to the screen for debugging.')
    parser.add_argument('-r','-radius',dest='radius',default=DISTWINDOW,
                        help='Specify distance window for search (km)  (default: %(default)s km.)')
    parser.add_argument('-e','-event',dest='eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('-y','-hypocenter',dest='Params',action=ValidateParams,nargs=3,metavar=('TIME','LAT','LON'),
                        help='Specify UTC time, lat and lon. (time format YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('-w','-window',dest='timeWindow',help='Specify time window for search (seconds) (default: %(default)s).',type=int,default=TIMEWINDOW)
    parser.add_argument('-f','-folder',dest='folder',help='Specify output station folder destination (defaults to event input folder or current working directory)')
    parser.add_argument('-u','-user',dest='user',help='Specify K-NET user (defaults to value in config)')
    parser.add_argument('-p','-password',dest='password',help='Specify K-NET password (defaults to value in config)')
    parser.add_argument('-n','-nuke',dest='nuke',action='store_true',default=False,
                        help='Do NOT retain extracted raw data files')
    parser.add_argument('-o','-plot',dest='doPlot',action='store_true',default=False,
                        help='Make QA plots')
    pargs = parser.parse_args()
    main(pargs,config)    
    

    
