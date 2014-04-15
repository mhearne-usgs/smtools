Introduction
------------

smtools is a library and a set of tools for downloading, calibrating, and converting earthquake strong motion
sensor data to peak ground motions, in a format suitable as input for the ShakeMap program.

Installation and Dependencies
-----------------------------

This package depends on:
 * numpy, the fundamental package for scientific computing with Python. <a href="http://www.numpy.org/">http://www.numpy.org/</a>  
 * matplotlib, a Python 2D plotting library which produces publication quality figures. <a href="<a href="http://matplotlib.org/index.html">http://matplotlib.org/index.html</a>
 * scipy, a Python library which provides many user-friendly and efficient numerical routines such as routines for numerical integration and optimization. <a href="<a href="http://www.scipy.org/scipylib/index.html">http://www.scipy.org/scipylib/index.html</a>
 * obspy, a Python library for dealing with seismology data.
 * neicio, a Python library for reading/writing various spatial data formats (including shakemap). 

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
usage: getknet.py [-h] [-c] [-i INPUTFOLDER] [-d] [-e EVENTID] [-t UTCTIME]
                  [-j JPTIME] [-w TIMEWINDOW] [-f FOLDER] [-u USER]
                  [-p PASSWORD] [-k] [-o]

Download and process K-NET strong motion data into peak ground motion values, and output in an
        XML format.
        Usage:
        To configure the system for further use (you will be prompted for KNET username/password, and ShakeMap home):
        getknet.py -c
        To process data from a local folder (rather than downloading from K-NET):
        getknet.py -i INPUTFOLDER -f OUTPUTFOLDER
        To process data from a local folder and print peak ground motions to the screen:
        getknet.py -i INPUTFOLDER -d
        To process data from an event at a particular UTC time, with a 75 second search window:
        ./getknet.py -f ~/tmp/knet -d -t 2014-04-02T23:22:47 -k -w 60

        ###############################################################
        For Shakemap Users:
        To download data for an event into it's input folder, while retaining the raw data:
        
        getknet.py -e EVENTID -k
        
        To download data for an event into it's input folder, while deleting the raw data:
        
        getknet.py -e EVENTID
        

optional arguments:
  -h, --help            show this help message and exit
  -c, -config           Create config file for future use
  -i INPUTFOLDER, -inputfolder INPUTFOLDER
                        process files from an input folder.
  -d, -debug            print peak ground motions to the screen for debugging.
  -e EVENTID, -event EVENTID
                        Specify event ID (will search ShakeMap data directory.
  -t UTCTIME, -utctime UTCTIME
                        Specify UTC Time for event. (format YYYY-MM-
                        DDTHH:MM:SS)
  -j JPTIME, -jptime JPTIME
                        Specify Japanese Standard Time for event. (format
                        YYYY-MM-DDTHH:MM:SS)
  -w TIMEWINDOW, -window TIMEWINDOW
                        Specify time window for search (seconds) (default:
                        60).
  -f FOLDER, -folder FOLDER
                        Specify output station folder destination (defaults to
                        event input folder or current working directory)
  -u USER, -user USER   Specify user (defaults to value in config)
  -p PASSWORD, -password PASSWORD
                        Specify password (defaults to value in config)
  -k, -keep             Retain extracted ASCII K-NET data files
  -o, -plot             Make QA plots
</pre>

