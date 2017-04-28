#!/usr/bin/env python
'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import sys
from ror import *

VERSION = '0.1'

def Usage():
    print '''
Usage: ror_cli [-h|--help]
       ror_cli [-v|--version]
       ror_cli cmd [-h|--help]
    where cmd may be:
       info              - print config info

       init-db           - load extension and creates schemas if needed 

       census-fetch      - download census data and load it into database

       naip-fetch [args] - based on area of interest in config.py fetch NAIP
            [-y year]      defaults to configured year
            [--no-shp]     don't fetch the shapefiles (presumes they are loaded
            [--no-naip]    don't fetch the naip imagery
            [--all-states] fetch all state shape files
            [--status]     report status on the naip inventory
            [-a|--area fips|bbox] only fetch DOQQs in this fips area or
                                  xmin,ymin,xmax,ymax bbox area

       naip-process      - convert raw NAIP imagery into a compress working set
            [-y|--year year] - naip year, defaults to config year
            [-n|-nproc n]    - num of process, defaults to config or 1, 0=all
            [-l|--limit n]   - limit number of files to process (for debugging)
            [-s|-sobel]      - invert the configured sobel setting
            [-f|--files file [file ...]] process this list of files, default
                             is all downloaded files not already processed

       segment           - segment some or all of area of interest
            [-a|--area fips|bbox]   - only process this fips area or
                                      xmin,ymin,xmax,ymax bbox area
            [-s|--spatialr int]     - spatial radius of neigborhood in pixels
            [-r|--ranger float]     - radiometric radius in multi-spectral space
            [-t|--thresh float]     - convergence threshold
            [-i|--max-iter int]     - max interation during convergence
            [-p|--rangeramp float]  - range radius coefficient where:
                                      y = rangeramp*x+ranger
            [-m|--minsize int]      - minimum segment size in pixels
            [-T|--tilesize int]     - size of tiles in pixels
            [-R|--ram int(MB)]      - available ram for processing
            [-j|--job name]         - unique job name, will be used to
                                      to create table to store segments in

       train             - train some or all of training area and save data

       search            - using saved training data search for objects

    use help option for details on the cmd usage.
'''
    sys.exit(2)


def Main(argv):
    if argv[0] in ('-h', '--help'):
        Usage()
    elif argv[0] in ('-v', '--version'):
        print "ror_cli: version: %s" % ( VERSION )
    elif argv[0] == 'info':
        Info()
    elif argv[0] == 'init-db':
        InitDB()
    elif argv[0] == 'census-fetch':
        CensusFetch()
    elif argv[0] == 'naip-fetch':
        FetchNaip( argv[1:] )
    elif argv[0] == 'naip-process':
        ProcessNaip(  argv[1:] )
    elif argv[0] == 'osm-buildings':
        pass
    elif argv[0] == 'segment':
        Segmentation( argv[1:] )
    elif argv[0] == 'train':
        pass
    elif argv[0] == 'search':
        pass
    else:
        print
        print "ERROR: unknown cmd or option (%s)" % (argv[0])
        Usage()

if __name__ == '__main__':

    if len(sys.argv) == 1:
        Usage()

    Main(sys.argv[1:])
