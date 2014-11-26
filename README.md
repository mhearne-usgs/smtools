TODO
____
 - Create a getamps.py script that will retrieve peak ground motions from various sources.

Introduction
------------

smtools is a library and a set of tools for downloading, calibrating, and converting earthquake strong motion
sensor data to peak ground motions, in a format suitable as input for the ShakeMap program.  It also provides a 
script to "clone" a (modern*) ShakeMap from the USGS web site.

*The ShakeMap must provide an info.xml file, which older versions of the ShakeMap software did not create.

Installation and Dependencies
-----------------------------

This package depends on:
 * numpy, the fundamental package for scientific computing with Python. <a href="http://www.numpy.org/">http://www.numpy.org/</a>  
 * matplotlib, a Python 2D plotting library which produces publication quality figures. <a href="<a href="http://matplotlib.org/index.html">http://matplotlib.org/index.html</a>
 * scipy, a Python library which provides many user-friendly and efficient numerical routines such as routines for numerical integration and optimization. <a href="<a href="http://www.scipy.org/scipylib/index.html">http://www.scipy.org/scipylib/index.html</a>
 * obspy, a Python library for dealing with seismology data.
 * neicio, a Python library for reading/writing various spatial data formats (including ShakeMap grid.xml). 

The best way to install numpy,matplotlib,and scipy is to use one of the Python distributions described here:

<a href="http://www.scipy.org/install.html">http://www.scipy.org/install.html</a>

Anaconda and Enthought distributions have been successfully tested with smtools.

Most of those distributions should include <em>pip</em>, a command line tool for installing and 
managing Python packages.  You will use pip to install the other dependencies and smtools itself.  
 
You may need to open a new terminal window to ensure that the newly installed versions of python and pip
are in your path.

To install obspy:

pip install obspy

To install neicio:

pip install git+git://github.com/usgs/neicio.git

To install smtools:

pip install git+git://github.com/mhearne-usgs/smtools.git

Uninstalling and Updating
-------------------------

To uninstall:

pip uninstall smtools

To update:

pip install -U git+git://github.com/mhearne-usgs/smtools.git

Command line usage
------------------

<pre>
usage: getstrong.py [-h] [-c] [-i INPUTFOLDER] [-d] [-r RADIUS] [-e EVENTID]
                    [-y TIME LAT LON] [-w TIMEWINDOW] [-f FOLDER] [-u USER]
                    [-p PASSWORD] [-n] [-o] [-q] [-v]
                    {knet,geonet,turkey,iran,iris,italy,unam}

        Download and process strong motion data from different sources
        (NZ GeoNet, JP K-NET, Turkey) into peak ground motion values,
        and output in an XML format suitable for inclusion in
        ShakeMap.  The output files will be named according to the
        input data source: knet_dat.xml, geonet_dat.xml, etc.
        
        Generic (non-ShakeMap) Usage:
        To configure the system for further use (you will be prompted for 
        KNET username/password, and ShakeMap home):
        getstrong.py knet -c
        To process data from a local folder (rather than downloading from a remote source):
        getstrong.py -i INPUTFOLDER -f OUTPUTFOLDER
        To process data from a local folder and print peak ground motions to the screen:
        getstrong.py -i INPUTFOLDER -d

        To retrieve data from K-NET with a user-supplied K-NET username/password:
        getstrong.py knet -f ~/tmp/knet -y 2014-05-04T20:18:24 34.862 139.312 -u fred -p SECRETPASSWD

        To retrieve data from GeoNet:
        getstrong.py geonet -f ~/tmp/knet -y 2014-01-20T02:52:44 40.660 175.814

        To retrieve data from Turkey:
        getstrong.py turkey -f ~/tmp/knet -y 2003-05-01T00:27:06 38.970 40.450

        ###############################################################
        For Shakemap Users:
        To download K-NET data for an event into the event "input" 
        folder (the -f option is unnecessary), while retaining the raw data in event "raw" folder:
        
        getstrong.py knet -e EVENTID
        
        To download K-NET data for an event into it's input folder, while deleting the raw data:
        
        getstrong.py knet -e EVENTID -n

        To download data from Turkey:
        getstrong.py turkey -e EVENTID

        To download data from GeoNet:
        getstrong.py geonet -e EVENTID
        
        To download data from IRIS:
        getstrong.py iris -e EVENTID
        
        To download data from Iran:
        Download the files from "Digital Records," copy onto your local machine
        (http://www.bhrc.ac.ir/portal/Default.aspx?tabid=635)
        getstrong.py iran -e EVENTID -i PATH WHERE DATA IS LOCATED
        
        To download data from Mexico:
        Select all boxes and download. Copy onto the your local machine
        getstrong.py unam -e EVENTID -i PATH WHERE DATA IS LOCATED
        
        To download data from Italy:
        Download ASCII corrected files. Copy onto your local machine
        getstrong.py italy -e EVENT ID -i PATH WHERE DATA IS LOCATED
        

positional arguments:
  {knet,geonet,turkey,iran,iris,italy,unam}
                        Specify strong motion data source.

optional arguments:
  -h, --help            show this help message and exit
  -c, -config           Create config file for future use
  -i INPUTFOLDER, -inputfolder INPUTFOLDER
                        process files from an input folder.
  -d, -debug            print peak ground motions to the screen for debugging.
  -r RADIUS, -radius RADIUS
                        Specify distance window for search (km) (default: 50
                        km.)
  -e EVENTID, -event EVENTID
                        Specify event ID (will search ShakeMap data directory.
  -y TIME LAT LON, -hypocenter TIME LAT LON
                        Specify UTC time, lat and lon. (time format YYYY-MM-
                        DDTHH:MM:SS)
  -w TIMEWINDOW, -window TIMEWINDOW
                        Specify time window for search (seconds) (default:
                        60).
  -f FOLDER, -folder FOLDER
                        Specify output station folder destination (defaults to
                        event input folder or current working directory)
  -u USER, -user USER   Specify K-NET user (defaults to value in config)
  -p PASSWORD, -password PASSWORD
                        Specify K-NET password (defaults to value in config)
  -n, -nuke             Do NOT retain extracted raw data files
  -o, -plot             Make QA plots
  -q, --noRotation      Do NOT apply rotation to IRAN longitudinal/transverse
                        channels
  -v, --verbose         Print out progress/warning messages
</pre>

<pre>
usage: smcheck.py [-h] eventID dataFile

Compare station data against a modeled ShakeMap.
        

positional arguments:
  eventID     Specify event ID (will search ShakeMap data directory.
  dataFile    Specify name of data file in event input folder to compare
              against ShakeMap grid.

optional arguments:
  -h, --help  show this help message and exit
</pre>

<pre>
usage: cloneshake.py [-h] url

Clone a ShakeMap from NEIC web site.
    
Examples:

    Cloning a scenario:
    cloneshake.py http://earthquake.usgs.gov/earthquakes/shakemap/global/shake/capstone2014_nmsw_m7.7_se/

    Cloning a real-time event:
    cloneshake.py http://comcat.cr.usgs.gov/earthquakes/eventpage/usb000slwn#summary
    

positional arguments:
  url         the URL of the desired ShakeMap.

optional arguments:
  -h, --help  show this help message and exit
</pre>
