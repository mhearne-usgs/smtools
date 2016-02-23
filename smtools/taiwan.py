#!/usr/bin/env python

GALS2PG = 9.81

def readTaiwan(fname):
    stationlist = []
    f = open(fname,'rt')
    for line in f.readlines():
        if line.find(':') > -1 or line.startswith('STA'):
            continue
        parts = line.split(',')
                
        code = '%s.%s' % ('CWB',parts[0].strip())
        name = parts[1].strip()
        lon = float(parts[2])
        lat = float(parts[3])
        channels = {}
        if len(parts) > 7:
            channels['HZ'] = {'pga':float(parts[4])/GALS2PG,'pgv':float(parts[7])}
            channels['HN1'] = {'pga':float(parts[5])/GALS2PG,'pgv':float(parts[8])}
            channels['HN2'] = {'pga':float(parts[6])/GALS2PG,'pgv':float(parts[9])}
        else:
            channels['HZ'] = {'pga':float(parts[4])/GALS2PG}
            channels['HN1'] = {'pga':float(parts[5])/GALS2PG}
            channels['HN2'] = {'pga':float(parts[6])/GALS2PG}
        stationdict = {'lat':lat,'lon':lon,'code':code,'name':name,
                       'channels':channels}
        stationlist.append(stationdict)
        
    f.close()
    return stationlist
                                   
                                   
    
