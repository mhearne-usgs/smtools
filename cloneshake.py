#!/usr/bin/env python

#stdlib imports
import os.path
import urllib2
import urlparse
from xml.dom.minidom import parseString
import sys
import StringIO
import argparse
import json
import datetime
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

GRIND_TEMPLATE = '''smVs30default : VS30DEFAULT
bad_station : 8016 9.9 19990101-
bad_station : 8010 9.9 19990101-
bad_station : 8022 9.9 19990101-
bad_station : 8034 9.9 19990101-
bad_station : 8040 9.9 19990101-

gmpe: GMPE 0.0 9.9 0 999
ipe: IPE 0.0 9.9 0 999
outlier_deviation_level : 3
outlier_max_mag         : 7.0

bias_norm         : l1
bias_max_range    : 120
bias_min_stations : 6
bias_max_mag      : 7.0
bias_max_bias     : 2.0
bias_min_bias     : -2.0
bias_log_amp      : true

direct_patch_size : 1000
topobin : <HOME>/bin/topo2grd <EVID> <BOUND> regime=active
mi2pgm : GMICE
pgm2mi : GMICE

source_network : us'''

def readInfo(infourl):
    try:
        fh = urllib2.urlopen(infourl)
        infoxml = fh.read()
        fh.close()
    except:
        raise Exception,'The supplemental file %s does not exist.' % infourl
    root = parseString(infoxml)
    tags = root.getElementsByTagName('tag')
    faultfile = None
    gmpe = None
    ipe = None
    gmice = None
    vs30 = 686
    for tag in tags:
        if tag.getAttribute('name') == 'faultfiles':
            faultfile = tag.getAttribute('value')
        if tag.getAttribute('name') == 'pgm2mi':
            value = tag.getAttribute('value')
            vparts = value.split()
            gmice = vparts[0].split('::')[2]
        if tag.getAttribute('name') == 'GMPE':
            value = tag.getAttribute('value')
            vparts = value.split()
            gmpe = vparts[0].split('::')[2]
        if tag.getAttribute('name') == 'IPE':
            value = tag.getAttribute('value')
            vparts = value.split()
            ipe = vparts[0].split('::')[2]
        if tag.getAttribute('name') == 'Vs30default':
            vs30 = int(tag.getAttribute('value'))
    root.unlink()
    return (gmpe,ipe,gmice,vs30,faultfile)

def getEventInfo(gridurl):
    gridfh = urllib2.urlopen(gridurl)
    gdata = gridfh.read()
    gridfh.close()

    gdata = gdata[0:gdata.find('<grid_data>')] + '</shakemap_grid>'
    xdom = parseString(gdata)
    root = xdom.getElementsByTagName('shakemap_grid')[0]
    infodict = {}
    infodict['id'] = root.getAttribute('event_id')
    event = root.getElementsByTagName('event')[0]
    infodict['lat'] = float(event.getAttribute('lat'))
    infodict['lon'] = float(event.getAttribute('lon'))
    infodict['depth'] = float(event.getAttribute('depth'))
    infodict['mag'] = float(event.getAttribute('magnitude'))
    timestr = event.getAttribute('event_timestamp')
    timestr = timestr[0:19]
    time = datetime.datetime(*strptime(timestr,"%Y-%m-%dT%H:%M:%S")[0:6])
    infodict['locstring'] = event.getAttribute('event_description')
    infodict['year'] = time.year
    infodict['month'] = time.month
    infodict['day'] = time.day
    infodict['hour'] = time.hour
    infodict['minute'] = time.minute
    infodict['second'] = time.second
    ctimestr = root.getAttribute('process_timestamp')
    ctimestr = ctimestr[0:19]
    ctime = datetime.datetime(*strptime(ctimestr,"%Y-%m-%dT%H:%M:%S")[0:6])
    infodict['created'] = ctime.strftime('%s')
    root.unlink()
    return infodict

def writeEvent(gmpe,ipe,gmice,vs30,faulturl,stationurl,eventdict,shakehome):
    #write the event.xml file
    datadir = os.path.join(shakehome,'data',eventdict['id'])
    inputdir = os.path.join(datadir,'input')
    confdir = os.path.join(datadir,'config')
    if not os.path.isdir(inputdir):
        os.makedirs(inputdir)
    if not os.path.isdir(confdir):
        os.makedirs(confdir)

    #write event.xml file
    eventfile = os.path.join(inputdir,'event.xml')
    f = open(eventfile,'wt')
    estr = EVENT_TEMPLATE
    for key,value in eventdict.iteritems():
        estr = estr.replace('['+key.upper()+']',str(value))
    f.write(estr)
    f.close()
    print 'Writing input file to %s' % eventfile

    #write stationlist.xml file (if it exists)
    try:
        fh = urllib2.urlopen(stationurl)
        data = fh.read()
        fh.close()
        datafile = os.path.join(inputdir,'stationlist.xml')
        f = open(datafile,'wt')
        f.write(data)
        f.close()
    except:
        print 'No stationlist file found.'
    
    #write fault file
    try:
        fh = urllib2.urlopen(faulturl)
        parts = urlparse.urlparse(faulturl)
        fpath = parts.path
        fbase,fname = os.path.split(fpath)
        faultfile = os.path.join(inputdir,fname)
        data = fh.read()
        fh.close()
        f = open(faultfile,'wt')
        f.write(data)
        f.close()
        print 'Writing fault file to %s' % faultfile
    except:
        print 'No fault file found.'

    #write grind.conf file
    grindfile = os.path.join(confdir,'grind.conf')
    f = open(grindfile,'wt')
    gstr = GRIND_TEMPLATE.replace('VS30DEFAULT',str(vs30))
    gstr = gstr.replace('GMPE',gmpe)
    gstr = gstr.replace('IPE',ipe)
    gstr = gstr.replace('GMICE',gmice)
    f.write(gstr)
    f.close()
    print 'Writing grind config to %s' % grindfile

def getShakeURLs(shakeurl):
    urlt = 'http://earthquake.usgs.gov/fdsnws/event/1/query?eventid=[EVENTID]&format=geojson'
    eventid = urlparse.urlparse(shakeurl).path.strip('/').split('/')[-1]
    url = urlt.replace('[EVENTID]',eventid)
    fh = urllib2.urlopen(url)
    data = fh.read()
    jdict = json.loads(data)
    fh.close()
    contentlist = jdict['properties']['products']['shakemap'][0]['contents'].keys()
    infourl = None
    gridurl = None
    stationurl = None
    faulturl = None
    for content in contentlist:
        if content.find('info.xml') > -1:
            infourl = jdict['properties']['products']['shakemap'][0]['contents'][content]['url']
        if content.endswith('grid.xml'):
            gridurl = jdict['properties']['products']['shakemap'][0]['contents'][content]['url']
        if content.find('stationlist.xml') > -1:
            stationurl = jdict['properties']['products']['shakemap'][0]['contents'][content]['url']
        if content.find('_fault.txt') > -1:
            faulturl = jdict['properties']['products']['shakemap'][0]['contents'][content]['url']
    return (infourl,faulturl,gridurl,stationurl)
    
def main(shakeurl):
    #remove any stuff after a # sign in the url
    if shakeurl.find('#') == -1:
        endidx = len(shakeurl)
    else:
        endidx = shakeurl.find('#')
    shakeurl = shakeurl[0:endidx]
    if not shakeurl.endswith('/'):
        shakeurl += '/'
    #shakeurl: http://earthquake.usgs.gov/earthquakes/shakemap/ut/shake/shakeoutff_se/
    #http://earthquake.usgs.gov/earthquakes/shakemap/ut/shake/shakeoutff_se/download/info.xml
    if sys.platform == 'darwin':
        shakehome = '/opt/local/ShakeMap'
    else:
        shakehome = '/home/shake/ShakeMap'
    #Is this a scenario?
    if shakeurl.find('_se') > -1:
        infourl = urlparse.urljoin(shakeurl,'download/info.xml')
        gridurl = urlparse.urljoin(shakeurl,'download/grid.xml')
        stationurl = urlparse.urljoin(shakeurl,'download/stationlist.xml')
        try:
            gmpe,ipe,gmice,vs30,faultfile = readInfo(infourl)
        except Exception,error:
            print 'There was a problem trying to clone the ShakeMap.\nError message:\n"%s".\nExiting.' % error.message
            sys.exit(1)
        faulturl = urlparse.urljoin(shakeurl,'download/%s' % faultfile)
    else:
        infourl,faulturl,gridurl,stationurl = getShakeURLs(shakeurl)
        gmpe,ipe,gmice,vs30,tmp = readInfo(infourl)
    
    eventdict = getEventInfo(gridurl)
    writeEvent(gmpe,ipe,gmice,vs30,faulturl,stationurl,eventdict,shakehome)
    print 'Cloning completed.\nTo run this event, do:\n%s/bin/shake -event %s' % (shakehome,eventdict['id'])
    

if __name__ == '__main__':
    desc = '''Clone a ShakeMap from NEIC web site.
    
Examples:

    Cloning a scenario:
    %(prog)s http://earthquake.usgs.gov/earthquakes/shakemap/global/shake/capstone2014_nmsw_m7.7_se/

    Cloning a real-time event:
    %(prog)s http://comcat.cr.usgs.gov/earthquakes/eventpage/usb000slwn#summary
    '''
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('url', help='the URL of the desired ShakeMap.')
    args = parser.parse_args()
    if not args.url:
        print parser.print_help()
        sys.exit(1)
    main(args.url)
