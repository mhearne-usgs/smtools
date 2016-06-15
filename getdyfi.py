#!/usr/bin/env python

#stdlib imports
import urllib.request, urllib.error, urllib.parse
import urllib.parse
import os.path
import argparse
import re
import json
from configparser import ConfigParser,RawConfigParser
from xml.dom import minidom
import sys
from datetime import datetime

#third party imports
from neicio.tag import Tag
from libcomcat import comcat 

#local imports
from smtools import util

EVENTURL = 'http://comcat.cr.usgs.gov/earthquakes/eventpage/[EVENTID].geojson'

def fetchCDIByParams(etime,lat,lon,config,rawfolder):
    eventlist = comcat.associate({'lat':lat,'lon':lon,'time':etime})
    if len(eventlist) == 0:
        msg = 'Could not find any events within %.1f km and %i seconds of event at %s (%.3f,%.3f)'
        print(msg % (comcat.DISTWINDOW,comcat.TIMEWINDOW,etime,lat,lon))
        sys.exit(1)
    if len(eventlist) > 1:
        msg = 'Found multiple events within %.1f km and %i seconds of event at %s (%.3f,%.3f).  Exiting.'
        print(msg % (comcat.DISTWINDOW,comcat.TIMEWINDOW,etime,lat,lon))
        sys.exit(1)
    url = EVENTURL.replace('[EVENTID]',eventlist[0]['id'])
    req = urllib.request.Request(url)
    req.add_unredirected_header('User-Agent', 'Custom User-Agent')
    fh = urllib.request.urlopen(req)
    data = fh.read()
    fh.close()
    jdict = json.loads(data)
    if 'dyfi' not in list(jdict['properties']['products'].keys()):
        print('DYFI product not found for event %s.  Exiting.' % etime)
        sys.exit(1)
    dyfi = jdict['properties']['products']['dyfi'][0]
    durl = None
    if 'cdi_geo.xml' in list(dyfi['contents'].keys()):
        durl = dyfi['contents']['cdi_geo.xml']['url']
    else:
        if 'cdi_zip.xml' in list(dyfi['contents'].keys()):
            durl = dyfi['contents']['cdi_zip.xml']['url']
        else:
            print('DYFI product not found for event %s.  Exiting.' % etime)
            sys.exit(1)
    fh = urllib.request.urlopen(durl)
    data = fh.read()
    fh.close()
    urlpath = urllib.parse.urlsplit(durl).path
    tmp,fname = os.path.split(urlpath)
    outfname = os.path.join(rawfolder,fname)
    f = open(outfname,'wt')
    f.write(data)
    f.close()
    return outfname

def fetchCDIByID(eventid,config,rawfolder):
    eventfile = os.path.join(config.get('SHAKEMAP','shakehome'),'data',eventid,'input','event.xml')
    etime,lat,lon = util.parseEvent(eventfile)
    return fetchCDIByParams(etime,lat,lon,config,rawfolder)

def readCDI(cdifile):
    root = minidom.parse(cdifile)
    #is there ever more than one cdi element?
    rootel = root.getElementsByTagName('cdidata')[0].getElementsByTagName('cdi')[0]
    locations = []
    stationlist = rootel.getElementsByTagName('location')
    for station in stationlist:
        sdict = {}
        sdict['name'] = station.getAttribute('name')
        sdict['name'] = re.sub(r'[^\x00-\x7F]+',' ', sdict['name'])
        sdict['lat'] = float(station.getElementsByTagName('lat')[0].firstChild.data)
        sdict['lon'] = float(station.getElementsByTagName('lon')[0].firstChild.data)
        sdict['dist'] = float(station.getElementsByTagName('dist')[0].firstChild.data)
        sdict['nresp'] = int(station.getElementsByTagName('nresp')[0].firstChild.data)
        sdict['cdi'] = float(station.getElementsByTagName('cdi')[0].firstChild.data)
        locations.append(sdict.copy())
    root.unlink()
    return locations

def writeCDI(outname,stationlist):
    stationlist_tag = Tag('stationlist',attributes={'created':datetime.utcnow().strftime('%s')})
    code = 0
    for station in stationlist:
        stationtag = Tag('station',attributes={'name':station['name'],
                                               'netid':'DYFI',
                                               'insttype':'OBSERVED',
                                               'source':'USGS (Did You Feel It?)',
                                               'lat':station['lat'],'lon':station['lon'],
                                               'loc':station['name'],
                                               'code':code,
                                               'intensity':'%.1f' % station['cdi']})
        code += 1        
        
        stationlist_tag.addChild(stationtag)
    stationlist_tag.renderToXML(filename=outname,ntabs=1)
    
def main(args,config):
    if args.eventID and config is None:
        print('To specify event ID, you must have configured the ShakeHome parameter in the config file.')
        print('Re-run with -config.  Returning.')
        sys.exit(1)

    #Get the output folder
    outfolder,rawfolder = util.getOutFolders(args,config)
    if not os.path.isdir(rawfolder):
        os.makedirs(rawfolder)

    if args.eventID:
        cdifile = fetchCDIByID(args.eventID,config,rawfolder)
    else:
        cdifile = fetchCDIByParams(args.Params.time,args.Params.lat,args.Params.lon,config,rawfolder)

    stationlist = readCDI(cdifile)
    tmp,fname = os.path.split(cdifile)
    fname,fext = os.path.splitext(fname)
    outname = fname+'_dat'+fext
    outname = os.path.join(outfolder,outname)
    writeCDI(outname,stationlist)
        
if __name__ == '__main__':
    #look for config file
    configfile = os.path.join(os.path.expanduser('~'),'.smtools','config.ini')
    pconfig = None
    if os.path.isfile(configfile):
        pconfig = ConfigParser()
        pconfig.readfp(open(configfile))

    desc = """Retrieve Did You Feel It? (DYFI) data from the NEIC ComCat system for a given event,
        convert into ShakeMap XML data file format.
        """
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter,)
    parser.add_argument('-e','-event',dest='eventID',help='Specify event ID (will search ShakeMap data directory.')
    parser.add_argument('-y','-hypocenter',dest='Params',action=util.ValidateParams,
                        nargs=3,metavar=('TIME','LAT','LON'),
                        help='Specify UTC time, lat and lon. (time format YYYY-MM-DDTHH:MM:SS)')    

    parser.add_argument('-f','-folder',dest='folder',
                        help='Specify output station folder destination (defaults to event input folder or current working directory)')
    pargs = parser.parse_args()
    main(pargs,pconfig)

    
