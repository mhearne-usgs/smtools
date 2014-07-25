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
from obspy.signal import rotate
import numpy as np
import matplotlib.pyplot as plt

FLOATMATCH = '[0-9]*\.?[0-9]+'
CHANNEL = {'VERT':'HLZ','N00E':'HLNS','N90E':'HLEW','N00W':'HLNS','N90W':'HLEW','V':'HLZ'}

def readunam(unamfile):
    f = open(unamfile,'rt')
    dataBlockCount = 0
    coordStart = False
    blockStart = False
    hdrdict = {}
    data = []
    for line in f.readlines():
        if line.startswith('----'):
            dataBlockCount += 1
            continue
        if line.startswith('CLAVE DE LA ESTACION'):
            hdrdict['station'] = line.split(':')[1].strip()
            continue
        if line.startswith('NOMBRE DE LA ESTACION'):
            hdrdict['station'] = line.split(':')[1].strip()
            continue
        if line.startswith('FECHA DEL SISMO'):
            year,mon,day = line.split(':')[1].split('/')
            year = int(year)
            mon = int(mon)
            day = int(day)
            continue
        if line.startswith('HORA DE LA PRIMERA MUESTRA'):
            hour,tmin,sec = line.split(':')[1:]
            hour = int(hour)
            tmin = int(tmin)
            sec = float(sec)
            msec = int((sec - np.floor(sec))*1000000)
            sec = int(np.floor(sec))
            hdrdict['starttime'] = UTCDateTime(year,mon,day,hour,tmin,sec,msec)
            continue
        if line.startswith('NOMBRE DE LA ESTACION'):
            hdrdict['location'] = line.split(':')[1].strip()
            continue
        if line.startswith('COORDENADAS DE LA ESTACION'):
            latstr = re.search(FLOATMATCH,line.split(':')[1].strip()).group()
            hdrdict['lat'] = float(latstr)
            coordStart = True
            continue
        if coordStart:
            lonstr = re.search(FLOATMATCH,line.split(':')[1].strip()).group()
            hdrdict['lon'] = float(lonstr)
            coordStart = False
            continue
        if line.startswith('ALTITUD'):
            hdrdict['height'] = float(line.split(':')[1].strip())
            continue
        if line.startswith('INTERVALO DE MUESTREO, C1-C6'):
            intstr = line.split(':')[1].strip().lstrip('/')
            intervals = [float(i) for i in intstr.split('/')]
            continue
        if line.startswith('DURACION DEL REGISTRO (s), C1-C6'):
            durstr = line.split(':')[1].strip().lstrip('/')
            durations = [float(i) for i in durstr.split('/')]
            continue
        if line.startswith('NUM. TOTAL DE MUESTRAS, C1-C6'):
            ptstr = line.split(':')[1].strip().lstrip('/')
            npts = [int(i) for i in ptstr.split('/')]
            continue
        if line.startswith('ORIENTACION C1-C6'):
            channels = line.split(':')[1].strip().lstrip('/').split('/')
            try:
                channels = [CHANNEL[ch] for ch in channels]
            except:
                pass
            continue
        if dataBlockCount == 2:
            data.append([float(d) for d in line.split()])
    f.close()
    hdrdict['network'] = 'MX'
    hdrdict['units'] = 'acc'
    alldata = np.array(data)/100.0 #convert from Gal (cm/s^2) to m/s^2

    #construct header and data array for channel 1
    hdr1 = hdrdict.copy()
    hdr1['sampling_rate'] = 1.0/intervals[0]
    hdr1['delta'] = intervals[0]
    hdr1['channel'] = channels[0]
    hdr1['npts'] = npts[0]
    hdr1['duration'] = durations[0]
    data1 = alldata[:,0]
    stats1 = Stats(hdr1)
    trace1 = Trace(data1,header=stats1)

    #construct header and data array for channel 2
    hdr2 = hdrdict.copy()
    hdr2['delta'] = intervals[1]
    hdr2['sampling_rate'] = 1./intervals[1]
    hdr2['channel'] = channels[1]
    hdr2['npts'] = npts[1]
    hdr2['duration'] = durations[1]
    data2 = alldata[:,1]
    stats2 = Stats(hdr2)
    trace2 = Trace(data2,header=stats2)

    #construct header and data array for channel 3
    hdr3 = hdrdict.copy()
    hdr3['delta'] = intervals[2]
    hdr3['sampling_rate'] = 1./intervals[2]
    hdr3['channel'] = channels[2]
    hdr3['npts'] = npts[2]
    hdr3['duration'] = durations[2]
    data3 = alldata[:,2]
    stats3 = Stats(hdr3)
    trace3 = Trace(data3,header=stats3)

    tracelist = [trace1,trace2,trace3]
    headerlist = [hdr1,hdr2,hdr3]

    return (tracelist,headerlist)
    

if __name__ == '__main__':
    unamfile = sys.argv[1]
    traces,headers = readunam(unamfile)
    trace = traces[0]
    trace.plot()
    plt.savefig('unam.png')
    print trace.data.max()
    print trace.stats['calib']
    print trace.data.max() * trace.stats['calib']
