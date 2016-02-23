#!/usr/bin/env python

#stdlib imports
import sys
import argparse
import glob
import os.path

#third party or local imports
from smtools.trace2xml import amps2xml
from smtools.taiwan import readTaiwan

SUPPORTED_NETWORKS = {'taiwan':'Taiwan Central Weather Bureau'}

def main(args):
    if args.listSources:
        print '%-15s\t%-40s' % ('Network','Description')
        print '------------------------------------------'
        for key,value in SUPPORTED_NETWORKS.iteritems():
            print '%-15s\t%-40s' % (key,value)
        sys.exit(0)

    if args.folder:
        outfolder = args.folder
    else:
        outfolder = os.getcwd()

    if not args.inputFolder:
        print 'Must specify input folder with -i.'
        sys.exit(1)

    if args.source == 'taiwan':
        txtfiles = glob.glob(os.path.join(args.inputFolder,'*.txt'))
        for txtfile in txtfiles:
            stationlist = readTaiwan(txtfile)
            datafile,tag = amps2xml(stationlist,outfolder,'CWB')
            print 'Created data file %s.' % datafile
    sys.exit(0)
        
if __name__ == '__main__':
    desc = '''Convert peak amplitude data from various sources into ShakeMap XML data file format.'''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('source',help='Specify strong motion data source.',choices=['taiwan'])
    parser.add_argument('-s','-sources',dest='listSources',action='store_true',default=False,
                        help='Describe various sources for strong motion data')
    parser.add_argument('-i','-inputfolder',dest='inputFolder',
                        help='process files from an input folder.')
    parser.add_argument('-f','-folder',dest='folder',help='Specify output station folder destination (defaults to event input folder or current working directory)')
    pargs = parser.parse_args()
    main(pargs)
    
