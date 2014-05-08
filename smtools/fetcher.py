class StrongMotionFetcher(object):
    def __init__(self):
        pass
    def fetch(self,lat,lon,time,radius,timewindow):
        pass

class StrongMotionFetcherException(Exception):
    """
    Handles exceptions in subclasses of StrongMotionFetcher
    """
