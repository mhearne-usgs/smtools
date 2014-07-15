from xml.dom import minidom
from datetime import datetime
import argparse
import os
import collections

TIMEFMT = '%Y-%m-%dT%H:%M:%S'

def maketime(timestring):
    outtime = None
    try:
        outtime = datetime.strptime(timestring,TIMEFMT)
    except:
        try:
            outtime = datetime.strptime(timestring,DATEFMT)
        except:
            raise Exception,'Could not parse time or date from %s' % timestring
    return outtime

def parseEvent(eventxml):
    root = minidom.parse(eventxml)
    eq = root.getElementsByTagName('earthquake')[0]
    year = int(eq.getAttribute('year'))
    month = int(eq.getAttribute('month'))
    day = int(eq.getAttribute('day'))
    hour = int(eq.getAttribute('hour'))
    minute = int(eq.getAttribute('minute'))
    second = int(eq.getAttribute('second'))
    utctime = datetime(year,month,day,hour,minute,second)
    lat = float(eq.getAttribute('lat'))
    lon = float(eq.getAttribute('lon'))
    root.unlink()
    return (utctime,lat,lon)


class ValidateParams(argparse.Action):
    """
    Validate time,lat,lon parameters (for use with argparse)
    """
    def __call__(self, parser, args, values, option_string=None):
        # print '{n} {v} {o}'.format(n=args, v=values, o=option_string)
        etimestr, latstr,lonstr = values
        try:
            etime = maketime(etimestr)
        except Exception,instance:
            raise ValueError('Invalid time string %s' % etimestr)
        try:
            lat = float(latstr)
        except:
            raise ValueError('Invalid latitude value %s' % latstr)
        try:
            lon = float(lonstr)
        except:
            raise ValueError('Invalid longitude value %s' % lonstr)
        Params = collections.namedtuple('Params', ['time','lat','lon'])
        setattr(args, self.dest, Params(etime,lat,lon))


def getOutFolders(args,config):
    """
    Get the event input and raw folders 
    """
    #There are three ways to specify the time of the desired earthquake
    #By event id:
    if args.eventID:
        if not args.folder:
            outfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'input')
            rawfolder = os.path.join(config.get('SHAKEMAP','shakehome'),'data',args.eventID,'raw')
        else:
            outfolder = args.folder
            rawfolder = args.folder
    else:
        if args.folder:
            outfolder = args.folder
            rawfolder = args.folder
        else:
            outfolder = os.getcwd()
            rawfolder = outfolder
    return (outfolder,rawfolder)
