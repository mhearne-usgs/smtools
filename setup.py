from distutils.core import setup

setup(name='smtools',
      version='0.1dev',
      description='NEIC ShakeMap Strong Motion Tools',
      author='Mike Hearne',
      author_email='mhearne@usgs.gov',
      url='',
      packages=['smtools'],
      scripts = ['getstrong.py','smcheck.py','getdyfi.py','cloneshake.py','createshake.py'],
)
