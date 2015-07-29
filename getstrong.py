#!/usr/bin/env python

#stdlib
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
#import numpy.oldnumeric

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
from smtools import knet,geonet,turkey,iran,iris,italy,unam,util,orfeus,chile
from smtools import trace2xml

#third party
from obspy.xseed import Parser
import obspy

#constants
TIMEWINDOW = 60 #number of seconds within which to search for matching event on knet/geonet site
DISTWINDOW = 50 #number of seconds within which to search for matching event on knet/geonet site

SUPPORTED_NETWORKS = {'knet':'Japanese Strong Motion (NIED)',
                      'geonet':'New Zealand (GNS)',
                      'turkey':'Turkish strong motion repository',
                      'iran':'Iranian strong motion repository',
                      'iris':'Incorporated Research Institutions for Seismology',
                      'italy':'Italian strong motion (INGV)',
                      'unam':'Mexican strong motion data (UNAM)',
                      'orfeus':'Integrated European strong motion data repository',
                      'SAC':'Any data in SAC format (must also provide dataless seed in input directory',
                      'chile':'Calibrated ASCII data from Chilean seismic network',
                      'pickle':'Calibrated strong motion data from any source',}

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
    if args.listSources:
        print '%-15s\t%-40s' % ('Network','Description')
        print '------------------------------------------'
        for key,value in SUPPORTED_NETWORKS.iteritems():
            print '%-15s\t%-40s' % (key,value)
        sys.exit(0)
        
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

    #Most formats are pre-calibrated, so we'll set parse to None for those.
    #Those formats that need a parser object (like SAC data files need a dataless SEED file)
    #will fill in the parser object below.
    parser = None
    datafiles = []
    if not args.inputFolder:
        if args.source == 'orfeus':
            stationlist = orfeus.getAmps(lat,lon,etime,args.timeWindow,args.radius)
            outfile,stationlist_tag = trace2xml.amps2xml(stationlist,outfolder,'orfeus')
            print 'Retrieved peak ground motions from %i European stations' % len(stationlist)
            sys.exit(0)
        if args.source == 'knet':
            if not args.user:
                user = config.get('KNET','user')
                password = config.get('KNET','password')
            else:
                user = args.user
                password = args.password
            sys.stderr.write('Fetching strong motion data from NIED...\n')
            fetcher = knet.KNETFetcher(user,password)
        elif args.source == 'geonet':
            sys.stderr.write('Fetching strong motion data from GeoNet...\n')
            fetcher = geonet.GeonetFetcher()
        elif args.source == 'turkey':
            sys.stderr.write('Fetching strong motion data from Turkey...\n')
            fetcher = turkey.TurkeyFetcher()
        elif args.source == 'iran':
            print 'Automated downloading of Iran strong motion data is not supported.  Use the -i option instead.'
            print 'Obtain strong motion records from: http://www.bhrc.ac.ir/portal/Default.aspx?tabid=635'
            sys.exit(1)
        elif args.source == 'sac':
            print 'Automated downloading of SAC strong motion data is not supported.  Use the -i option instead.'
            print 'SAC is a data standard, not a source.  You will need to have obtained SAC data from your own source.'
            sys.exit(1)
        elif args.source == 'chile':
            print 'Automated downloading of Chilean calibrated ASCII strong motion data is not supported.  Use the -i option instead.'
            sys.exit(1)
        elif args.source == 'pickle':
            print 'Automated downloading of Chilean calibrated ASCII strong motion data is not supported.  Use the -i option instead.'
            sys.exit(1)
        elif args.source == 'iris':
            sys.stderr.write('Fetching strong motion and broadband data from IRIS...\n')
            fetcher = iris.IrisFetcher(verbose=args.verbose) #will get strong motion AND broadband
        elif args.source == 'italy':
            print 'Automated downloading of Italian strong motion data is not supported.  Use the -i option instead.'
            sys.exit(1)
        elif args.source == 'unam':
            print 'Automated downloading of Mexican (UNAM) strong motion data is not supported.  Use the -i option instead.'
            sys.exit(1)
        else:
            print 'Data source %s not supported.' % args.source
            sys.exit(1)
        try:
            datafiles = fetcher.fetch(lat,lon,etime,args.radius,args.timeWindow,rawfolder)
        except Exception,e:
            print '(Possible) error in trying to download data from %s.  \n"%s"\n' % (args.source,str(e))
        sys.stderr.write('Retrieved %i files.\n' % len(datafiles))
    else: 
        
        if not os.path.isdir(args.inputFolder):
            print 'Could not find folder "%s".  Exiting.' % args.inputFolder
            sys.exit(1)
        if args.source == 'orfeus':
            print 'Offline data processing not supported for Orfeus.'
            sys.exit(1)
        if args.source == 'knet':
            datafiles1 = glob.glob(os.path.join(args.inputFolder,'*.NS'))
            datafiles2 = glob.glob(os.path.join(args.inputFolder,'*.EW'))
            datafiles3 = glob.glob(os.path.join(args.inputFolder,'*.UD'))
            datafiles = datafiles1+datafiles2+datafiles3
        elif args.source == 'geonet':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.V1A'))
        elif args.source == 'turkey':
            datafiles1 = glob.glob(os.path.join(args.inputFolder,'*.txt'))
            datafiles = []
            for d in datafiles1:
                dpath,dfile = os.path.split(d)
                if re.match('[0-9]{4}',dfile) is not None:
                    datafiles.append(d)
        elif args.source == 'iran':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.V1'))
        elif args.source == 'chile':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.asc'))
        elif args.source == 'pickle':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.pickle'))
        elif args.source == 'iris':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.pickle'))
        elif args.source == 'italy':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*DAT'))
        elif args.source == 'sac':
            datafiles = glob.glob(os.path.join(args.inputFolder,'*.sac'))
            seedfiles = glob.glob(os.path.join(args.inputFolder,'*.seed'))
            if not len(seedfiles):
                print 'A dataless SEED file (ending in .seed) must be supplied with input SAC files. Exiting.'
                sys.exit(1)
            parser = Parser(seedfiles[0])
        elif args.source == 'unam':
            tdatafiles = glob.glob(os.path.join(args.inputFolder,'*')) #grab everything
            datafiles = []
            for dfile in tdatafiles:
                fname,fext = os.path.splitext(dfile)
                if re.match('\d',fext[1:]) is not None:
                    datafiles.append(dfile)
        else:
            print 'Data source %s not supported.' % args.source
            sys.exit(1)
        
    
    traces = []
    for dfile in datafiles:
        if args.source == 'knet':
            if dfile.endswith('1'): #these files are KikNet downhole (deep) stations
                continue
            trace,header = knet.readknet(dfile)
            traces.append(trace)
        elif args.source == 'geonet':
            tracelist,headers = geonet.readgeonet(dfile)
            traces = traces + tracelist
        elif args.source == 'turkey':
            tracelist,headers = turkey.readturkey(dfile)
            traces = traces + tracelist
        elif args.source == 'iran':
            doRotation = True
            if args.noRotation:
                doRotation = False
            tracelist,headers = iran.readiran(dfile,doRotation=doRotation)
            traces = traces + tracelist
        elif args.source == 'iris':
            trace = iris.readiris(dfile)
            traces.append(trace)
        elif args.source == 'italy':
            trace = italy.readitaly(dfile)
            traces.append(trace)
        elif args.source == 'chile':
            trace = chile.readchile(dfile)
            traces.append(trace)
        elif args.source == 'pickle':
            stream = obspy.core.read(dfile)
            for trace in stream:
                traces.append(trace)
        elif args.source == 'unam':
            tracelist,headers = unam.readunam(dfile)
            traces = traces + tracelist
        elif args.source == 'sac':
            stream = obspy.read(dfile)
            for trace in stream:
                traces.append(trace)
        else:
            print 'Source %s is not supported' % (args.source)
            sys.exit(1)
    if len(datafiles):
        sys.stderr.write('Converting %i files to peak ground motion...\n' % len(datafiles))
        stationfile,plotfiles,tag = trace2xml.trace2xml(traces,parser,outfolder,args.source,doPlot=args.doPlot)
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
        ShakeMap.  The output files will be named according to the
        input data source: knet_dat.xml, geonet_dat.xml, etc.
        
        Generic (non-ShakeMap) Usage:
        To configure the system for further use (you will be prompted for 
        KNET username/password, and ShakeMap home):
        getstrong.py knet -c

        To list all of the networks and their descriptions:
        getstrong.py knet -s (still necessary to supply a data source, which is arguably kind of stupid)
        Network        	Description                             
        ------------------------------------------
        turkey         	Turkish strong motion repository        
        iris           	Incorporated Research Institutions for Seismology
        iran           	Iranian strong motion repository        
        geonet         	New Zealand (GNS)                       
        knet           	Japanese Strong Motion (NIED)           
        italy          	Italian strong motion (INGV)            
        orfeus         	Integrated European strong motion data repository
        unam           	Mexican strong motion data (UNAM) 
        sac             (Not a network) Data files in SAC format.
        
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

        To process local SAC data (input directory must contain one or more SAC files with 
        file extension .sac, and one dataless SEED file with extension .seed:
        getstrong.py sac -i /mydata/sacfiles -f /home/shake/ShakeMap/data/EVENT/input

        ###############################################################
        For Shakemap Users:
        To download K-NET data for an event into the event "input" 
        folder (the -f option is unnecessary), while retaining the raw data in event "raw" folder:
        
        getstrong.py knet -e EVENTID
        
        To download K-NET data for an event into it's input folder, while deleting the raw data:
        
        getstrong.py knet -e EVENTID -n

        To download data from Turkey:
        getstrong.py turkey -e EVENTID

        To download data from GeoNet:
        getstrong.py geonet -e EVENTID
        
        To download data from IRIS:
        getstrong.py iris -e EVENTID
        
        To download data from Iran:
        Download the files from "Digital Records," copy onto your local machine
        (http://www.bhrc.ac.ir/portal/Default.aspx?tabid=635)
        getstrong.py iran -e EVENTID -i PATH WHERE DATA IS LOCATED
        
        To download data from Mexico:
        Select all boxes and download. Copy onto the your local machine
        getstrong.py unam -e EVENTID -i PATH WHERE DATA IS LOCATED
        
        To download data from Italy:
        Download ASCII corrected files. Copy onto your local machine
        getstrong.py italy -e EVENT ID -i PATH WHERE DATA IS LOCATED
        '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('source',help='Specify strong motion data source.',choices=['knet','geonet','turkey','iran',
                                                                                    'iris','italy','unam','orfeus',
                                                                                    'sac','chile','pickle'])
    parser.add_argument('-s','-sources',dest='listSources',action='store_true',default=False,
                        help='Describe various sources for strong motion data')
    parser.add_argument('-c','-config',dest='doConfig',action='store_true',default=False,
                        help='Create config file for future use')
    parser.add_argument('-i','-inputfolder',dest='inputFolder',
                        help='process files from an input folder.')
    parser.add_argument('-d','-debug',dest='debug',action='store_true',default=False,
                        help='print peak ground motions to the screen for debugging.')
    parser.add_argument('-r','-radius',dest='radius',default=DISTWINDOW,type=float,
                        help='Specify distance window for search (km)  (default: %(default)s km.)')
    parser.add_argument('-e','-event',dest='eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('-y','-hypocenter',dest='Params',action=util.ValidateParams,nargs=3,metavar=('TIME','LAT','LON'),
                        help='Specify UTC time, lat and lon. (time format YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('-w','-window',dest='timeWindow',help='Specify time window for search (seconds) (default: %(default)s).',type=int,default=TIMEWINDOW)
    parser.add_argument('-f','-folder',dest='folder',help='Specify output station folder destination (defaults to event input folder or current working directory)')
    parser.add_argument('-u','-user',dest='user',help='Specify K-NET user (defaults to value in config)')
    parser.add_argument('-p','-password',dest='password',help='Specify K-NET password (defaults to value in config)')
    parser.add_argument('-n','-nuke',dest='nuke',action='store_true',default=False,
                        help='Do NOT retain extracted raw data files')
    parser.add_argument('-o','-plot',dest='doPlot',action='store_true',default=False,
                        help='Make QA plots')
    parser.add_argument('-q','--noRotation',dest='noRotation',action='store_true',default=False,
                        help='Do NOT apply rotation to IRAN longitudinal/transverse channels')
    parser.add_argument('-v','--verbose',dest='verbose',action='store_true',default=False,
                        help='Print out progress/warning messages')
    pargs = parser.parse_args()
    main(pargs,config)    
    

    
