'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import os
import re
import psycopg2
import subprocess
from config import *
from utils import unique, \
                  getDatabase, \
                  getStatesCountiesFromBbox, \
                  loadZippedShape


def CensusFetch():
    baseurl = CONFIG.get('census.url', '')
    verbose = CONFIG.get('verbose', False)
    year    = CONFIG.get('census.year', '')

    if baseurl == '' or year == '':
        print "ERROR in config.py, census.url or census.year are not defined!"
        sys.exit(2)

    # make dir the outdir path exists
    outdir = CONFIG['projectHomeDir'] + '/data/census/'
    if not os.path.exists( outdir ):
        os.makedirs( outdir )

    # -------------- fetch the county data -----------------------------
    if True:
        url = baseurl + '/' + '/'.join(CONFIG['census.layers']['county'])
        url = url % ( year, year )

        cmd = ['wget', '-o', outdir + 'county.log',
               '-N', '-nv', '-nd', '-nH', '-P', outdir, url]
        if verbose:
            print ' '.join(cmd)
        subprocess.call(cmd)

        zipfile = r'.*_county\.zip$'
        loadZippedShape( 'census.county', outdir, zipfile, 'PROMOTE_TO_MULTI' )


    # -------------- deal with area of interest ------------------------
    #
    # this needs to be after county data is loaded
    # because we search that against the BBOX
    #
    # this might be a FIPS code or a BBOX list
    aoi = CONFIG.get('areaOfInterest', '')
    if type(aoi) == str and len(aoi) == 0:
        print "areaOfInterest is disabled in config.py"
        sys.exit(2)
    elif type(aoi) == list:
        conn, cur = getDatabase()
        states, counties = getStatesCountiesFromBbox( cur, CONFIG['areaOfInterest'] )
        conn.close()
    else:
        states = [ aoi[:2] ]
        if len(aoi) >= 5:
            counties = [ aoi[:5] ]
        elif len(aoi) == 2:
            counties = [ aoi[:2] + '*' ]
        else:
            counties = [ '*' ]

    # make sure we have at least 1 county
    if len(states) == 0:
        print "ERROR: no counties were selected!"
        sys.exit(2)

    # -------------- fetch cousub data ----------------------------------
    if True:
        url = baseurl + '/' + CONFIG['census.layers']['cousub'][0] + '/'
        url = url % ( year )

        for ss in states:
            fzip = CONFIG['census.layers']['cousub'][1] % ( year, ss )
            cmd = ['wget', '-o', outdir + 'cousub.log',
                   '-N', '-nv', '-nd', '-nH', '-P', outdir, url + fzip]
            if verbose:
                print ' '.join(cmd)
            subprocess.call(cmd)

        zipfile = r'.*_cousub\.zip$'
        loadZippedShape( 'census.cousub', outdir, zipfile, 'PROMOTE_TO_MULTI' )


    # -------------- fetch roads data -----------------------------------
    if True:
        url = baseurl + '/' + CONFIG['census.layers']['roads'][0] + '/'
        url = url % ( year )

        for cc in counties:
            fzip = CONFIG['census.layers']['roads'][1] % ( year, cc )
            cmd = ['wget', '-o', outdir + 'roads.log',
                   '-N', '-nv', '-nd', '-nH', '-P', outdir, url + fzip]
            if verbose:
                print ' '.join(cmd)
            subprocess.call(cmd)

        zipfile = r'.*_roads\.zip$'
        loadZippedShape( 'census.roads', outdir, zipfile, 'MULTILINESTRING' )


