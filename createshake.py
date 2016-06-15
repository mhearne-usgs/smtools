#!/usr/bin/env python

#stdlib imports
import os.path
import urllib.request, urllib.error, urllib.parse
import urllib.parse
from xml.dom.minidom import parseString
import sys
import io
import argparse
import json
from datetime import datetime,timedelta
from time import strptime

EVENT_TEMPLATE = '''<?xml version="1.0" encoding="US-ASCII" standalone="yes"?>
<!DOCTYPE earthquake [
<!ELEMENT  earthquake EMPTY>
<!ATTLIST earthquake
  id            ID      #REQUIRED
  lat           CDATA   #REQUIRED
  lon           CDATA   #REQUIRED
  mag           CDATA   #REQUIRED
  year          CDATA   #REQUIRED
  month         CDATA   #REQUIRED
  day           CDATA   #REQUIRED
  hour          CDATA   #REQUIRED
  minute        CDATA   #REQUIRED
  second        CDATA   #REQUIRED
  timezone      CDATA   #REQUIRED
  depth         CDATA   #REQUIRED
  type          CDATA   #REQUIRED
  locstring     CDATA   #REQUIRED
  pga           CDATA   #REQUIRED
  pgv           CDATA   #REQUIRED
  sp03          CDATA   #REQUIRED
  sp10          CDATA   #REQUIRED
  sp30          CDATA   #REQUIRED
  created       CDATA   #REQUIRED
>
]>
<earthquake id="[ID]" lat="[LAT]" lon="[LON]" mag="[MAG]" year="[YEAR]" month="[MONTH]" day="[DAY]" hour="[HOUR]" minute="[MINUTE]" second="[SECOND]" timezone="GMT" depth="[DEPTH]" locstring="[LOCSTRING]" created="[CREATED]" network="us" />'''


TIMEFMT = '%Y-%m-%dT%H:%M:%S'
BASEURL = 'http://earthquake.usgs.gov/fdsnws/event/1/query?eventid=[EVENT]&format=geojson'

def getEventInfo(weburl):
    eventdict = {}
    parts = urllib.parse.urlsplit(weburl.rstrip('/'))
    eventid = parts.path.split('/')[-1]
    url = BASEURL.replace('[EVENT]',eventid)
    fh = urllib.request.urlopen(url)
    data = fh.read()
    fh.close()
    jdict = json.loads(data)
    eventdict['lon'],eventdict['lat'],eventdict['depth'] = jdict['geometry']['coordinates']
    ms_since_epoch = jdict['properties']['time']
    sec_since_epoch = ms_since_epoch/1000
    microseconds = int((ms_since_epoch/1000.0 - sec_since_epoch)*1e6)
    eventdict['time'] = datetime.utcfromtimestamp(sec_since_epoch)
    eventdict['time'] += timedelta(microseconds = microseconds)
    eventdict['mag'] = jdict['properties']['mag']
    eventdict['locstring'] = jdict['properties']['place']
    eventdict['id'] = eventid
    return eventdict

def writeEvent(eventdict,shakehome):
    efolder = os.path.join(shakehome,eventdict['id'])
    if not os.path.isdir(efolder):
        os.makedirs(efolder)
    inputfolder = os.path.join(efolder,'input')
    if not os.path.isdir(inputfolder):
        os.makedirs(inputfolder)
    configfolder = os.path.join(efolder,'config')
    if not os.path.isdir(configfolder):
        os.makedirs(configfolder)

    eventdata = EVENT_TEMPLATE.replace('[ID]',eventdict['id'])
    eventdata = eventdata.replace('[LAT]','%.4f' % eventdict['lat'])
    eventdata = eventdata.replace('[LON]','%.4f' % eventdict['lon'])
    eventdata = eventdata.replace('[DEPTH]','%.1f' % eventdict['depth'])
    eventdata = eventdata.replace('[MAG]','%.1f' % eventdict['mag'])
    eventdata = eventdata.replace('[LOCSTRING]',eventdict['locstring'])
    epochtime = (eventdict['time'] - datetime(1970,1,1)).total_seconds()
    eventdata = eventdata.replace('[CREATED]','%i' % epochtime)
    eventdata = eventdata.replace('[YEAR]','%i' % eventdict['time'].year)
    eventdata = eventdata.replace('[MONTH]','%i' % eventdict['time'].month)
    eventdata = eventdata.replace('[DAY]','%i' % eventdict['time'].day)
    eventdata = eventdata.replace('[HOUR]','%i' % eventdict['time'].hour)
    eventdata = eventdata.replace('[MINUTE]','%i' % eventdict['time'].minute)
    eventdata = eventdata.replace('[SECOND]','%i' % eventdict['time'].second)
    eventfile = os.path.join(inputfolder,'event.xml')
    f = open(eventfile,'wt')
    f.write(eventdata)
    f.close()
    return efolder

def parseParams(params):
    eventdict = {}
    try:
        eventdict['time'] = datetime.strptime(params[0],TIMEFMT)
        eventdict['lat'] = float(params[1])
        eventdict['lon'] = float(params[2])
        eventdict['depth'] = float(params[3])
        eventdict['mag'] = float(params[4])
        eventdict['id'] = eventdict['time'].strftime('%Y%m%d%H%M%S')
        eventdict['locstring'] = '(%.4f,%.4f)' % (eventdict['lat'],eventdict['lon'])
    except Exception as excobj:
        raise excobj
    return eventdict
    
def main(args):
    if sys.platform == 'darwin':
        shakehome = '/opt/local/ShakeMap/data/'
    else:
        shakehome = '/home/shake/ShakeMap/data/'
    if args.url:
        #remove any stuff after a # sign in the url
        url = args.url[0:args.url.find('#')]
        if not url.endswith('/'):
            url += '/'
        eventdict = getEventInfo(url)
    else:
        eventdict = parseParams(args.params)
        
    efolder = writeEvent(eventdict,shakehome)
    print('Completed creating ShakeMap %s.\nTo run this event, do:\n%s/bin/shake -event %s' % (efolder,shakehome,eventdict['id']))

if __name__ == '__main__':
    desc = '''Create a ShakeMap from NEIC web site or from scratch.
    
Examples:
    Creating a ShakeMap from an event in ComCat:
    %(prog)s -u http://comcat.cr.usgs.gov/earthquakes/eventpage/usb000slwn#summary

    Creating a ShakeMap ab novo:
    %(prog)s -p 2015-01-01T13:45:59 34.3 -118.1 20.5 6.3 => will be assigned ID of us20150101134559
    '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-u','--url', help='the URL of the desired event in ComCat.')
    parser.add_argument('-p','--params', nargs=5,
                        help='the 5 params defining a ShakeMap input (time (YYYY-MM-DDTHH:MM:SS),lat,lon,depth,mag.')
    pargs = parser.parse_args()
    #must have at least one set
    if (pargs.url is None and pargs.params is None) or (pargs.url is not None and pargs.params is not None):
        print(parser.print_help())
        sys.exit(1)
    main(pargs)
