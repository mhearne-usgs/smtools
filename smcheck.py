#!/usr/bin/env python -W ignore::DeprecationWarning

#stdlib imports
import sys
import os.path
import glob
from ConfigParser import ConfigParser,RawConfigParser
import argparse

#third party imports
from neicio.shake import ShakeGrid
from xml.dom import minidom
import numpy as np
import matplotlib.pyplot as plt
from obspy.core.util.geodetics import gps2DistAzimuth

def main(args,config):
    eventid = args.eventID
    shakehome = config.get('SHAKEMAP','shakehome')
    xmlfile = os.path.join(shakehome,'data',eventid,'input',args.dataFile)
    gridfile = os.path.join(shakehome,'data',eventid,'output','grid.xml')
    #list of grid.xml variable names and corresponding data file variable names
    variables = [('PGA','acc'),('PGV','vel'),('PSA03','psa03'),('PSA10','psa10'),('PSA30','psa30')]

    shakemap = ShakeGrid(gridfile,variable='MMI') #doesn't matter
    gdict = shakemap.getGeoDict()
    atts = shakemap.getAttributes()
    location = atts['event']['event_description']
    etime = atts['event']['event_timestamp']
    epilat = atts['event']['lat']
    epilon = atts['event']['lon']
    nrows = gdict['nrows']
    ncols = gdict['ncols']
    
    root = minidom.parse(xmlfile)
    f = plt.figure(figsize=(8.5,11))
    pnum = 1
    pgaobs = []
    pgaexp = []
    pgadist = []
    for vartuple in variables:
        gridvar,stationvar = vartuple
        shakemap = ShakeGrid(gridfile,variable=gridvar)
        
        stations = root.getElementsByTagName('station')
        observed = []
        expected = []
        for i in range(0,len(stations)):
            station = stations[i]
            lat = float(station.getAttribute('lat'))
            lon = float(station.getAttribute('lon'))
            row,col = shakemap.getRowCol(lat,lon)
            if row < 0 or row > nrows or col < 0 or col > ncols:
                continue
            pgael = station.getElementsByTagName('comp')[0].getElementsByTagName(stationvar)[0]
            pga = float(pgael.getAttribute('value'))
            gridpga = shakemap.getValue(lat,lon)
            observed.append(pga)
            expected.append(gridpga)
            if gridvar == 'PGA':
                pgaobs.append(pga)
                pgaexp.append(gridpga)
                distance,az1,az2 = gps2DistAzimuth(epilat,epilon,lat,lon)
                pgadist.append(distance/1000.0)

        observed = np.array(observed)
        expected = np.array(expected)
        xmax = observed.max()
        ymax = expected.max()
        dmax = max(xmax,ymax) * 1.05
        v = [0,dmax,0,dmax]
        plt.subplot(3,2,pnum)
        plt.plot(observed,expected,'b.')
        plt.xlabel('Observed %s' % gridvar)
        plt.ylabel('Modeled %s' % gridvar)
        plt.axis(v)
        pnum += 1

    #Add in one final plot - pga differences vs distance, just to see if that's a factor
    pgaobs = np.array(pgaobs)
    pgaexp = np.array(pgaexp)
    pgadist = np.array(pgadist)
    pgadiff = np.power((pgaobs-pgaexp),2)
    mdiff = np.mean(pgadiff)
    stddiff = np.std(pgadiff)
    ymax = mdiff + 2*stddiff
    plt.subplot(3,2,6)
    plt.plot(pgadist,pgadiff,'b.')
    plt.ylabel('pga diff (squared)')
    plt.xlabel('Distance (km)')
    plt.axis([0,pgadist.max(),0,ymax])
    f.suptitle('Event %s %s - %s' % (eventid,etime.strftime('%Y-%m-%d %H:%M:%S'),location))
    plt.savefig('%s_qa.pdf' % eventid)

if __name__ == '__main__':
    #look for config file
    configfile = os.path.join(os.path.expanduser('~'),'.smtools','config.ini')
    config = None
    if os.path.isfile(configfile):
        config = ConfigParser()
        config.readfp(open(configfile))
        
    desc = '''Compare station data against a modeled ShakeMap.
        '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('dataFile',
                        help='Specify name of data file in event input folder to compare against ShakeMap grid.')
    pargs = parser.parse_args()
    main(pargs,config)
                        
    

    
