#!/usr/bin/env python

#stdlib imports
import sys
import os.path
from datetime import datetime

#third party imports
from obspy import read
from obspy.signal.freqattributes import pgm
from neicio.tag import Tag
from obspy.xseed.parser import Parser
import matplotlib.pyplot as plt

FILTER_FREQ = 0.02
CORNERS = 4
PSA03FREQ = 3.333
PSA10FREQ = 1.0
PSA30FREQ = 0.333
DAMPING = 0.05

def trace2xml(traces,parser,outfolder):
    """
    @param trace - ObsPy Trace object
    @param parser - ObsPy Parser object
    @outfolder - Path where output data XML files should be written.
    """
    #Make the top level tag - stationlist
    stationlist_tag = Tag('stationlist',attributes={'created':datetime.utcnow().strftime('%s')})
    for trace in traces:
        net = trace.stats['network']
        station = trace.stats['station']
        location = trace.stats['location']
        channel = trace.stats['channel']
        channel_id = '%s.%s.%s.%s' % (net,station,location,channel)
        paz = parser.getPAZ(channel_id)
        coordinates = parser.getCoordinates(channel_id)

        delta = trace.stats['sampling_rate']
        trace.detrend('simple')
        trace.detrend('demean')
        trace.taper()
        trace.simulate(paz_remove=paz,remove_sensitivity=True,simulate_sensitivity=False)
        trace.filter('highpass',freq=FILTER_FREQ,zerophase=True,corners=CORNERS)
        trace.detrend('simple')
        trace.detrend('demean')
        trace.integrate() #default cumtrapz - trace now has velocity
        #plot the velocity in a top plot
        plt.subplot(2,1,1)
        plt.plot(trace.data)
        plt.title('Velocity')
        plt.ylabel('m/s')
        trace.detrend('simple')
        trace.detrend('demean')
        trace.integrate() #trace now has displacement
        plt.subplot(2,1,2)
        plt.plot(trace.data)
        plt.title('Displacement')
        plt.ylabel('m')
        pngfile = os.path.join(outfolder,'%s.png' % channel_id)
        plt.savefig(pngfile)
        (psa03,disp,vel,pga) = pgm(trace.data, 1/delta, PSA03FREQ,damp=DAMPING)
        (psa10,tmp1,tmp2,tmp3) = pgm(trace.data, 1/delta, PSA10FREQ,damp=DAMPING)
        (psa30,tmp1,tmp2,tmp3) = pgm(trace.data, 1/delta, PSA30FREQ,damp=DAMPING)

        #convert accelerations to %g and cm/s
        psa03 = psa03/0.098
        psa10 = psa10/0.098
        psa30 = psa30/0.098
        pga = pga/0.098
        vel = vel * 100

        vdict = parser.getInventory()
        station_name = 'UNK'
        for sta in vdict['stations']:
            if sta['station_id'] == '%s.%s' % (net,station):
                station_name = sta['station_name']
                break
        instrument = 'UNK'
        for cha in vdict['channels']:
            if cha['channel_id'] == '%s.%s' % (net,station):
                instrument = cha['instrument']
                break

        #make the tags for the individual measurements
        psa03tag = Tag('psa03',attributes={'value':psa03})
        psa10tag = Tag('psa10',attributes={'value':psa10})
        psa30tag = Tag('psa30',attributes={'value':psa30})
        acctag = Tag('acc',attributes={'value':pga})
        veltag = Tag('vel',attributes={'value':vel})

        #make the component tag to hold the measurements
        comptag = Tag('comp',attributes={'name':channel})
        comptag.addChild(acctag)
        comptag.addChild(veltag)
        comptag.addChild(psa03tag)
        comptag.addChild(psa10tag)
        comptag.addChild(psa30tag)
        code = '%s.%s' % (net,station)
        lat = coordinates['latitude']
        lon = coordinates['longitude']
        stationtag = Tag('station',attributes={'code':code,'name':station_name,
                                               'insttype':instrument,'source':'',
                                               'netid':net,'commtype':'DIG',
                                               'lat':lat,'lon':lon,
                                               'loc':station_name})
        stationtag.addChild(comptag)
        stationlist_tag.addChild(stationtag)

    outfile = os.path.join(outfolder,'%s_dat.xml' % channel_id)
    print 'Saving to %s' % outfile
    stationlist_tag.renderToXML(filename=outfile,ntabs=1)

if __name__ == '__main__':
    seedfile = sys.argv[1]
    sacfiles = sys.argv[2:]
    parser = Parser(seedfile)
    traces = []
    for sacfile in sacfiles:
        stream = read(sacfile)
        traces.append(stream[0])
    trace2xml(traces,parser,os.getcwd())
