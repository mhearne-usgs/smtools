#!/usr/bin/env python

#define an interactive matplotlib backend
import matplotlib
matplotlib.use('TkAgg')

#stdlib
from collections import OrderedDict
import sys
import os.path
import argparse

#third party
import matplotlib.pyplot as plt
import numpy as np
from obspy.core.utcdatetime import UTCDateTime

from smtools import knet,geonet,turkey,iran,iris,italy,unam,util,orfeus,chile

def readheader(fname):
    hdrdict = OrderedDict()
    f = open(fname,'rt')
    for line in f.readlines():
        if line.startswith('#'):
            parts = line.strip('#').strip().split(':')
            key = parts[0].strip()
            value = ':'.join(parts[1:])
            hdrdict[key] = value.strip()
        else:
            break
    f.close()
    return hdrdict

def trim(toff):
    stime = TRACE.stats['starttime']
    etime = stime + toff
    TRACE.trim(stime,etime)
    fpath,fname = os.path.split(CURRENT_FILE)
    fname,fext = os.path.splitext(fname)
    outfile = os.path.join(fpath,fname+'.pickle')
    print 'Trimming trace from %s to %s' % (stime,etime)
    print 'Saving trimmed file to %s' % outfile
    TRACE.write(outfile,format='PICKLE')
    
    
def onclick(event):
    global XCLICK
    global YCLICK
    #print 'button=%d, x=%d, y=%d, xdata=%f, ydata=%f'%(event.button, event.x, event.y, event.xdata, event.ydata)
    if event.button == 1: #left button to mark
        XCLICK = event.xdata
        YCLICK = event.ydata
        print 'Clip Time: %s' % (TRACE.stats['starttime'] + event.xdata)
        plt.gca()
        xmin,xmax,ymin,ymax = plt.axis()
        plt.plot([event.xdata,event.xdata],[ymin,ymax],'r')
        plt.show()
        return
    if event.button == 3: #right button to accept
        trim(XCLICK)

def main(args):
    if args.doTrim is False:
        print 'Select the pre-processing option you want to use.  See help for list of currently supported options.'
        sys.exit(1)
    for dfile in args.files:
        global CURRENT_FILE
        CURRENT_FILE = dfile
        traces = []
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
        for trace in traces:
            global TRACE
            TRACE = trace
            fig = plt.figure(figsize=(10,10))

            plt.plot(trace.times(),trace.data,'b')
            cid = fig.canvas.mpl_connect('button_press_event', onclick)
            station = trace.stats['station']
            channel = trace.stats['channel']
            ts = '%s.%s\nLeft click to select, right click to accept, close plot when done' % (station,channel)
            plt.title(ts)
            xmin,xmax,ymin,ymax = plt.axis()

            #set 30 ticks
            xlocs = np.linspace(xmin,xmax,num=30)
            xlabels = []
            for xloc in xlocs:
                xtime = trace.stats['starttime'] + xloc
                xtimestr = xtime.strftime('%H:%M:%S')
                xlabels.append(xtimestr)

            plt.xticks(xlocs,xlabels,rotation=-90)

            plt.hold(True)
            for xloc in xlocs:
                plt.plot([xloc,xloc],[ymin,ymax],'k')

            plt.show()
            fig.canvas.mpl_disconnect(cid)
    sys.exit(0)
            
if __name__ == '__main__':
    #these are used to mark where the user clicks
    XCLICK = None
    YCLICK = None
    CURRENT_FILE = None
    TRACE = None
    desc = '''Pre-process data in any of the formats supported by getstrong.py. Currently supported: trimming.
    Example: 
    Trim Chile ASCII files:

    filtertrace.py -t chile ~/data/chile2/GO01_HN*.asc

    For each channel in each sensor, an interactive plot will appear.  To select the new ending time for the
    trace, left click on the plot.  A vertical red line will be drawn at that location.  Right click to accept
    that time, and close the window to proceed to the next trace.
    '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source',help='Specify strong motion data source.',choices=['knet','geonet','turkey','iran',
                                                                                    'iris','italy','unam','orfeus',
                                                                                    'sac','chile'])
    parser.add_argument('files',help='Filenames to process.',nargs="+")
    parser.add_argument('-t','--trim',dest='doTrim',action='store_true',default=False,
                        help='Interactively trim the latter part of a trace.')
    pargs = parser.parse_args()
    main(pargs)
    fname = sys.argv[1]
    trace = readchile(fname)

