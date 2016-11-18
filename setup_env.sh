#!/bin/bash

VENV=smtoolsenv
PYVER=3.5

DEPARRAY=(numpy scipy matplotlib obspy beautifulsoup4 rasterio pandas shapely h5py gdal pytest pytest pytest-cov pytest-mpl cartopy basemap)

#turn off whatever other virtual environment user might be in
source deactivate
    
#remove any previous virtual environments called smtools
CWD=`pwd`
cd $HOME;
conda remove --name $VENV --all -y
cd $CWD
    
#create a new virtual environment called $VENV with the below list of dependencies installed into it
conda create --name $VENV --yes --channel conda-forge python=$PYVER ${DEPARRAY[*]} -y

#activate the new environment
source activate $VENV

#install some items separately
#conda install -y sqlalchemy #at the time of this writing, this is v1.0, and I want v1.1
conda install -y psutil

#do pip installs of those things that are not available via conda.
pip install git+git://github.com/kallstadt-usgs/seisk.git
pip install git+git://github.com/usgs/neicio.git
pip install git+git://github.com/usgs/neicmap.git
pip -v install https://github.com/usgs/MapIO/archive/master.zip

#tell the user they have to activate this environment
echo "Type 'source activate ${VENV}' to use this new virtual environment."
