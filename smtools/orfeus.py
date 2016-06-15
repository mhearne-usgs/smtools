#!/usr/bin/env python

#stdlib imports
from datetime import datetime,timedelta
import urllib.request, urllib.error, urllib.parse
from xml.dom import minidom
import os.path
import re
import sys
import json
import math

#local imports
from neicmap.distance import sdist
from .trace2xml import amps2xml

#third party
from bs4 import BeautifulSoup

BASEURL = 'http://145.23.252.222:8080/opencms/rrsm/select-events/results/index.html?start=[START]&end=[END]&minmag=0.0&maxmag=9.9&minlat=20&maxlat=81&minlon=-32&maxlon=51&maxdepth=1000'
EVENTURL = 'http://145.23.252.222:8080/opencms/rrsm/select-events/results/event-detail/index.html?eventid=[EVENTID]'
DETAILURL = 'http://145.23.252.222:8080/opencms/rrsm/select-events/results/event-detail/station-detail/index.html?eventid=[EVENTID]&net=[NET]&sta=[STA]'


DATEFMT = '%Y-%m-%d'
TIMEFMT = '%Y-%m-%d %H:%M:%S'
FLOATPAT = '[+-]?(?=\d*[.eE])(?=\.?\d)\d*\.?\d*(?:[eE][+-]?\d+)?'

def getEventList(url):
    fh = urllib.request.urlopen(url)
    data = fh.read().decode('utf-8')
    fh.close()
    tstart = data.find('<tbody>')
    tend = data.find('</tbody>')+len('</tbody>')
    if tstart < 0:
        return []
    xmlstr = data[tstart:tend]
    xmlstr = xmlstr.replace('&','')
    try:
        root = minidom.parseString(xmlstr)
    except Exception as msg:
        pass
    rows = root.getElementsByTagName('tr')
    eventlist = []
    for row in rows:
        eventdict = {}
        cells = row.getElementsByTagName('td')
        eventdict['id'] = cells[0].getElementsByTagName('input')[0].getAttribute('value')
        eventdict['time'] = datetime.strptime(cells[1].firstChild.data.strip(),TIMEFMT)
        eventdict['lat'] = getCoord(cells[2].firstChild.data.strip())
        eventdict['lon'] = getCoord(cells[3].firstChild.data.strip())
        eventdict['depth'] = float(cells[4].firstChild.data.strip())
        eventdict['mag'] = float(re.search(FLOATPAT,cells[5].firstChild.data.strip()).group())
        eventlist.append(eventdict.copy())
    root.unlink()
    return eventlist

def getChannels(durl):
    fh = urllib.request.urlopen(durl)
    data = fh.read().decode('utf-8')
    fh.close()
    tstart = data.find('<tbody>')
    tend = data.find('</tbody>')+len('</tbody>')
    xmlstr = data[tstart:tend]
    soup = BeautifulSoup(xmlstr)
    rows = soup.findAll('tr')
    channeldict = {}
    for row in rows:
        cdict = {}
        cells = row.findAll('td')
        cname = cells[1].contents[0].strip()
        try:
            cdict['pga'] = getNumber(cells[3].contents[0].strip())
        except:
            pass
        cdict['pgv'] = getNumber(cells[4].contents[0].strip())
        try:
            cdict['psa03'] = getNumber(cells[5].contents[0].strip())
        except:
            pass
        cdict['psa10'] = getNumber(cells[6].contents[0].strip())
        cdict['psa30'] = getNumber(cells[7].contents[0].strip())
        channeldict[cname] = cdict.copy()

    return channeldict

def getCoord(coordstr):
    coord = float(re.search(FLOATPAT,coordstr).group())
    if coordstr.find('S') > -1 or coordstr.find('W') > -1:
        coord = coord*-1
    return coord

def getNumber(numberstr):
    try:
        number = float(re.search(FLOATPAT,numberstr).group())
    except:
        number = float('nan')
    return number

def getStationList(eurl,eventid):
    fh = urllib.request.urlopen(eurl)
    data = fh.read().decode('utf-8')
    fh.close()
    tstart = data.find('<tbody>')
    tend = data.find('</tbody>')+len('</tbody>')
    xmlstr = data[tstart:tend]
    #xmlstr = xmlstr.replace('&nbsp',' ')
    xmlstr = xmlstr.replace('&','')
    root = minidom.parseString(xmlstr)
    rows = root.getElementsByTagName('tr')
    stationlist = []
    ic = 0
    lastdec = 0
    #print len(rows)
    sys.stderr.write('% Progress:\n')
    sys.stderr.write('0...')
    for row in rows:
        pct = math.floor((ic/float(len(rows)))*100/10)*10
        #print ic,pct
        if pct > lastdec:
            lastdec += 10
            sys.stderr.write('%i...' % lastdec)
        stationdict = {}
        cells = row.getElementsByTagName('td')
        stationdict['code'] = cells[1].firstChild.data.strip()
        
        net,sta = stationdict['code'].split('.')
        stationdict['lat'] = getCoord(cells[2].firstChild.data.strip())
        stationdict['lon'] = getCoord(cells[3].firstChild.data.strip())
        stationdict['name'] = cells[5].firstChild.data.strip()
        durl = DETAILURL.replace('[EVENTID]',eventid)
        durl = durl.replace('[NET]',net)
        durl = durl.replace('[STA]',sta)
        channeldict = getChannels(durl)
        stationdict['channels'] = channeldict.copy()
        stationlist.append(stationdict)
        ic += 1
    sys.stderr.write('\n')
    return stationlist
        

def getAmps(lat,lon,etime,radius,timewindow):
    starttime = datetime(etime.year,etime.month,etime.day-1)
    endtime = datetime(etime.year,etime.month,etime.day+1)
    url = BASEURL.replace('[START]',starttime.strftime(DATEFMT))
    url = url.replace('[END]',endtime.strftime(DATEFMT))
    eventlist = getEventList(url)
    eventid = None
    for event in eventlist:
        elat = event['lat']
        elon = event['lon']
        if etime >= event['time']:
            dtime = etime - event['time']
        else:
            dtime = event['time'] - etime
        dt = dtime.days*86400 + dtime.seconds
        dd = sdist(lat,lon,elat,elon)/1000.0
        if dt < timewindow/2 and dd < radius:
            eventid = event['id']
            break
    if eventid is None:
        print('No events found matching your criteria.')
        return []
    eurl = EVENTURL.replace('[EVENTID]',eventid)
    stationlist = getStationList(eurl,eventid)
    return stationlist
            
if __name__ == '__main__':
    url = sys.argv[1]
    url = url.replace('#summary','')
    url += '.json'
    fh = urllib.request.urlopen(url)
    data = fh.read()
    fh.close()
    jdict = json.loads(data)
    etime = datetime.utcfromtimestamp(int(jdict['summary']['time'])/1000)
    lat = float(jdict['summary']['latitude'])
    lon = float(jdict['summary']['longitude'])
    radius = 25 #km
    timewindow = 4 #seconds
    stationlist = getAmps(lat,lon,etime,radius,timewindow,os.getcwd())
    outfile,stationlist_tag = trace2xml.ampsToXML(stationlist,os.getcwd(),'orfeus')
    # for station in stationlist:
    #     print '%s (%.4f,%.4f):' % (station['name'],station['lat'],station['lon'])
    #     for channelkey,channeldict in station['channels'].iteritems():
    #         fmt = '\t%s: PGA %.2f PGV %.2f PSA0.3 %.2f PSA1.0 %.2f PSA3.0 %.2f'
    #         tpl = (channelkey,channeldict['pga'],channeldict['pgv'],
    #                channeldict['psa03'],channeldict['psa10'],channeldict['psa30'])
    #         print fmt % tpl
    
