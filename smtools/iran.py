#!/usr/bin/env python

import warnings
warnings.simplefilter("ignore", DeprecationWarning)
import numpy.oldnumeric

#stdlib imports
from datetime import datetime,timedelta
import sys
import os.path
import re

#local
from trace2xml import trace2xml
import util

#third party
from obspy.core.trace import Trace
from obspy.core.trace import Stats
from obspy.core.utcdatetime import UTCDateTime
from obspy.core.util.geodetics import gps2DistAzimuth
import numpy as np
import matplotlib.pyplot as plt

INTIMEFMT = '%Y/%m/%d %H:%M:%S'
FLOATRE = "[-+]?[0-9]*\.?[0-9]+."
INTRE = "[-+]?[0-9]*"

def readheader(lines):
    hdrdict = {}
    #input list of 27 lines of header

    #assume the file name is the station for now
    line = lines[0]
    parts = line.split(':')
    hdrdict['station'] = parts[1].strip().replace('/','-')
    
    #read the origin/start time
    line = lines[2]
    parts = line.split()
    hdrdict['starttime'] = UTCDateTime(datetime.strptime(parts[3]+' '+parts[4],INTIMEFMT))

    #read the location information and station lat/lon
    line = lines[7]
    parts = line.split('Station')
    location = parts[0].strip().replace(' ','_')
    hdrdict['location'] = location
    coords = re.findall(FLOATRE,parts[1].strip())
    hdrdict['lat'] = float(coords[0])
    hdrdict['lon'] = float(coords[1])
    try:
        hdrdict['height'] = float(re.search(INTRE,coords[2]).group())
    except:
        pass
    
    #read the station azimuth info - we will need it to rotate the horizontal data back to EW and NS
    parts2 = parts[1].split('Azimuth')
    parts2 = parts2[1].split()
    rotation = {parts2[0]:int(parts2[1]),parts2[2]:int(parts2[3])}
    hdrdict['rotation'] = rotation

    #read the period and duration
    line = lines[20]
    parts = line.strip().split()
    hdrdict['delta'] = float(parts[0])
    hdrdict['sampling_rate'] = 1/hdrdict['delta']
    hdrdict['duration'] = float(parts[2])

    #read the number of points and duration
    line = lines[10]
    parts = line.split('=')
    hdrdict['npts'] = int(re.search(INTRE,parts[1].strip()).group())

    #read the channel (component)
    line = lines[6]
    parts = line.strip().split()
    hdrdict['channel'] = parts[1]

    hdrdict['calib'] = 1.0
    hdrdict['network'] = 'IR'
    return hdrdict
    

def readheaderlines(f):
    hdrlines = []
    for i in range(0,27):
        hdrlines.append(f.readline())
    return hdrlines

def readiran(iranfile):
    """
    Read strong motion data from a Iran data file
    @param iranfile: Path to a valid Iran data file.
    @return: List of ObsPy Trace objects, containing accelerometer data in m/s.
    """
    f = open(iranfile,'rt')
    tracelist = []
    headerlist = []
    try:
        hdrlines = readheaderlines(f)
    except:
        pass
    while len(hdrlines[-1]):
        hdrdict = readheader(hdrlines)
        numlines = int(np.ceil(hdrdict['npts']/10.0))
        data = []
        for i in range(0,numlines):
            line = f.readline()
            parts = line.strip().split()
            mdata = [float(p) for p in parts]
            data = data + mdata
        data = np.array(data)
        header = hdrdict.copy()
        stats = Stats(hdrdict)
        trace = Trace(data,header=stats)
        #apply the calibration and convert from mm/s^2 to m/s^2
        trace.data = trace.data * trace.stats['calib'] * 0.98 #convert to m/s^2 from g/10
        tracelist.append(trace.copy())
        headerlist.append(header.copy())
        endblock = f.readline()
        hdrlines = readheaderlines(f)

    f.close()
    return (tracelist,headerlist)

if __name__ == '__main__':
    iranfile = sys.argv[1]
    traces,headers = readiran(iranfile)
    trace = traces[0]
    trace.plot()
    plt.savefig('iran.png')
    print trace.data.max()
    print trace.stats['calib']
    print trace.data.max() * trace.stats['calib']
    #stationfile,plotfiles,tag = trace2xml(traces,None,os.getcwd(),doPlot=True)
