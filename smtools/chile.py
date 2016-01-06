#!/usr/bin/env python

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
from obspy.signal import rotate
import numpy as np
import matplotlib.pyplot as plt

INTIMEFMT = '%Y-%m-%dT%H:%M:%S'
FLOATRE = "[-+]?[0-9]*\.?[0-9]+."
INTRE = "[-+]?[0-9]*"


def readchile(ascfile):
    """
    Read strong motion data from an ASCII data file from Chile.
    @param ascfile: Path to a valid ASCII data file.
    @return: List of ObsPy Trace objects, containing accelerometer data in m/s.
    """
    f = open(ascfile,'rt')
    tracelist = []
    hdrdict = {}
    startdata = False
    data = []
    for line in f.readlines():
        if line.startswith('#'):
            if line.startswith('# Tiempo'):
                parts = line.split()
                hdrdict['starttime'] = UTCDateTime(parts[4])
                continue
            elif line.startswith('# Tasa'):
                parts = line.split()
                hdrdict['sampling_rate'] = float(parts[4])
                continue
            elif line.startswith('# Numero'):
                parts = line.split(':')
                hdrdict['npts'] = int(parts[1])
                continue
            elif line.startswith('# Estacion'):
                parts = line.split(':')
                hdrdict['station'] = parts[1].strip()
                hdrdict['channel'] = parts[2].strip()
                continue
            elif line.startswith('# Componente'):
                parts = line.split(':')
                hdrdict['channel'] = parts[1].strip()
                continue
            elif line.startswith('# Latitud'):
                parts = line.split()
                hdrdict['lat'] = float(parts[2])
                hdrdict['lon'] = float(parts[4])
                continue
            elif line.startswith('# Unidades'):
                parts = line.split(':')
                units = parts[1].strip()
                if units == 'm/seg/seg':
                    calib = 1.0
                elif units == 'g':
                    calib = 9.8
                else:
                    raise ValueError('Unsupported units of "%s".' % units)
                continue
        else:
            data.append(float(line.strip()))
    data = np.array(data)
    data *= calib
    hdrdict['calib'] = calib
    hdrdict['delta'] = 1.0/hdrdict['sampling_rate']
    hdrdict['duration'] = hdrdict['starttime'] + hdrdict['delta']*hdrdict['npts']
    hdrdict['network'] = 'C1' #chile doesn't put network in their headers, so we have to guess here.  C1 is the right answer sometimes.
    hdrdict['units'] = 'acc'
    hdrdict['height'] = 0.0
    stats = Stats(hdrdict)
    trace = Trace(data,header=stats)
    return trace

if __name__ == '__main__':
    ascfile = sys.argv[1]
    traces = readchile(ascfile)
    trace = traces[0]
    trace.plot()
    plt.savefig('chile.png')
    print trace.data.max()
    print trace.stats['calib']
    print trace.data.max() * trace.stats['calib']
    #stationfile,plotfiles,tag = trace2xml(traces,None,os.getcwd(),doPlot=True)
