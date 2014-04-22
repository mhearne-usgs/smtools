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

#import local
from smtools import knet,geonet
from smtools.trace2xml import trace2xml

#constants
FTPBASE = 'ftp://www.k-net.bosai.go.jp/knet/alldata/[YEAR]/[MONTH]'
TIMEFMT = '%Y-%m-%dT%H:%M:%S'
TIMEWINDOW = 60 #number of seconds within which to search for matching event on knet/geonet site
DISTWINDOW = 50 #number of seconds within which to search for matching event on knet/geonet site

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

    mytarfile = None
    datafiles = []
    if not args.inputFolder:
        if args.source == 'knet':
            sys.stderr.write('Fetching strong motion data from NIED...\n')
            mytarfile,datafiles = knet.getDataFiles(args,config,rawfolder,args.timeWindow)
        if args.source == 'geonet':
            sys.stderr.write('Fetching strong motion data from GeoNet...\n')
            datafiles = geonet.getDataFiles(config,rawfolder,args.timeWindow,args.radius,eventid=args.eventID,eventtime=args.UTCTime)
            mytarfile = None
        else:
            print 'You must specify a source for the strong motion data.'
            sys.exit(1)
        sys.stderr.write('Retrieved %i files.\n' % len(datafiles))
    else: #this is specific to K-NET - fix!
        datafiles1 = glob.glob(os.path.join(args.inputFolder,'*.NS'))
        datafiles2 = glob.glob(os.path.join(args.inputFolder,'*.EW'))
        datafiles3 = glob.glob(os.path.join(args.inputFolder,'*.UD'))
        datafiles = datafiles1+datafiles2+datafiles3
    
    traces = []
    for dfile in datafiles:
        if args.source == 'knet':
            trace,header = knet.readknet(dfile)
            traces.append(trace)
        elif args.source == 'geonet':
            tracelist,headers = geonet.readgeonet(dfile)
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
    
    if mytarfile is not None:
        os.remove(mytarfile)
    #if the user specified an input folder, but did not specify to keep, keep anyway
    if args.inputFolder:
        args.keeptar = True
    if not args.keep:
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
        desc = '''Download and process strong motion data from different sources (NZ GeoNet, JP K-NET) into peak ground motion values, and output in an XML format.
        Usage:
        To configure the system for further use (you will be prompted for KNET username/password, and ShakeMap home):
        getknet.py -c
        To process data from a local folder (rather than downloading from K-NET):
        getknet.py -i INPUTFOLDER -f OUTPUTFOLDER
        To process data from a local folder and print peak ground motions to the screen:
        getknet.py -i INPUTFOLDER -d
        To process data from an event at a particular UTC time, with a 75 second search window:
        ./getknet.py -f ~/tmp/knet -d -t 2014-04-02T23:22:47 -k -w 60

        ###############################################################
        For Shakemap Users:
        To download data for an event into it's input folder, while retaining the raw data:
        
        getknet.py -e EVENTID -k
        
        To download data for an event into it's input folder, while deleting the raw data:
        
        getknet.py -e EVENTID
        '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('source',help='Specify strong motion data source.',choices=['knet','geonet'])
    parser.add_argument('-c','-config',dest='doConfig',action='store_true',default=False,
                        help='Create config file for future use')
    parser.add_argument('-i','-inputfolder',dest='inputFolder',
                        help='process files from an input folder.')
    parser.add_argument('-d','-debug',dest='debug',action='store_true',default=False,
                        help='print peak ground motions to the screen for debugging.')
    parser.add_argument('-r','-radius',dest='radius',default=DISTWINDOW,
                        help='Specify distance window for search (seconds).')
    parser.add_argument('-e','-event',dest='eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('-t','-utctime',dest='UTCTime',help='Specify UTC Time for event. (format YYYY-MM-DDTHH:MM:SS)',type=maketime)
    
    parser.add_argument('-w','-window',dest='timeWindow',help='Specify time window for search (seconds) (default: %(default)s).',type=int,default=TIMEWINDOW)
    parser.add_argument('-f','-folder',dest='folder',help='Specify output station folder destination (defaults to event input folder or current working directory)')
    parser.add_argument('-u','-user',dest='user',help='Specify user (defaults to value in config)')
    parser.add_argument('-p','-password',dest='password',help='Specify password (defaults to value in config)')
    parser.add_argument('-k','-keep',dest='keep',action='store_true',default=False,
                        help='Retain extracted ASCII K-NET data files')
    parser.add_argument('-o','-plot',dest='doPlot',action='store_true',default=False,
                        help='Make QA plots')
    pargs = parser.parse_args()
    main(pargs,config)    
    

    
