from xml.dom import minidom
from datetime import datetime

def parseEvent(eventxml):
    root = minidom.parse(eventxml)
    eq = root.getElementsByTagName('earthquake')[0]
    year = int(eq.getAttribute('year'))
    month = int(eq.getAttribute('month'))
    day = int(eq.getAttribute('day'))
    hour = int(eq.getAttribute('hour'))
    minute = int(eq.getAttribute('minute'))
    second = int(eq.getAttribute('second'))
    root.unlink()
    utctime = datetime(year,month,day,hour,minute,second)
    return utctime
