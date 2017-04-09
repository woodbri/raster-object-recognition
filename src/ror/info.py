'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

from config import *

def Info():
    '''Print config and other project information.'''

    requiredKeys = ['dbname', 'dbuser', 'dbhost', 'dbport', 'dbpass',
        'census.url', 'naip.url', 'osm.url']

    ok = True
    for k in requiredKeys:
        if not CONFIG.has_key(k):
            print "ERROR: config.CONFIG is missing required key %s" % ( k )
            ok = False
    if not ok:
        sys.exit(1)

    # Database parameters
    print "Database:"
    print "    dbname:", CONFIG['dbname']
    print "    dbhost:", CONFIG['dbhost']
    print "    dbport:", CONFIG['dbport']
    print "    dbuser:", CONFIG['dbuser']
    print "    dbpass:", '*' * max(len(CONFIG['dbpass']),1)
    print
    print "URLs:"
    print "    census.url:", CONFIG['census.url']
    print "    naip.url:", CONFIG['naip.url']
    print "    osm.url:", CONFIG['osm.url']
    print


