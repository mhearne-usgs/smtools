#!/usr/bin/env python

#stdlib
from datetime import datetime
import re
import sys
import os.path

#local
from trace2xml import trace2xml

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
import numpy as np
import matplotlib.pyplot as plt

TIMEFMT = '%Y/%m/%d %H:%M:%S'
KNET_TRIGGER_DELAY = 15.0 #a delay in the KNet data logger - subtract this from "record time"

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
    
    
    
