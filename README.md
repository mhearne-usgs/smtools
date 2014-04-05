smtools
=======

USGS ShakeMap data processing tools 

These tools are meant for processing strong motion, macro-seismic, and peak ground motion data so that they can be used as input data for the ShakeMap program.

At the time of this writing, this repository consists of one function in trace2xml.py:

trace2xml(trace,parser,outfolder):
 - trace ObsPy Trace object
 - parser ObsPy Parser object
 - outfolder Path where output data XML files should be written.
        
