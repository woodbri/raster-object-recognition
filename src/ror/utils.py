'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import os
import sys
import re
import subprocess
import psycopg2
from config import *

DEVNULL = open(os.devnull, 'w')


def unique(seq, idfun=None):
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result



def runCommand(cmd, verbose):
    if verbose:
        print ' '.join( cmd )
        subprocess.call( cmd )
    else:
        subprocess.call( cmd, stdout=DEVNULL, stderr=subprocess.STDOUT )



def getDatabase():

    try:
        conn = psycopg2.connect( CONFIG['dsn'] )
    except:
        print "ERROR: failed to connect to database '%s'" % ( CONFIG['dbname'] )
        sys.exit(1)

    conn.set_session(autocommit=True)
    cur = conn.cursor()

    return ( conn, cur )




def parseBBOX(bbox):

    bbox = bbox.strip("BOX() ")
    tmp = bbox.split(',')
    (xmin, ymin) = tmp[0].split()
    (xmax, ymax) = tmp[1].split()
    return [float(xmin), float(ymin), float(xmax), float(ymax)]



def getBboxFromFIPS(cur, fips):

    if len(fips) == 2:
        sql = "select Box2D(st_extent(geom)) from census.county where statefp='%s'" % (fips)
    elif len(fips) == 5:
        sql = "select Box2D(st_extent(geom)) from census.county where geoid='%s'" % ( fips )
    elif len(fips) == 10:
        sql = "select Box2D(st_extent(geom)) from census.cousub where geoid='%s'" % ( fips )
    else:
        print "ERROR: fips code must be ss[ccc[bbbbb]]!"
        sys.exit(2)

    cur = conn.cursor()
    cur.execute( sql )
    row = cur.fetchone()

    return parseBBOX(row[0])



def getDoqqFiles( cur, bbox ):

    table = CONFIG.get('naip.shptable', '')
    doqqs = CONFIG.get('naip.doqq_dir', '')
    if table == '' or doqqs == '':
        print "ERROR: naip.shptable: '%s' or naip.doqq_dir: '%s' are not set in config.py!"
        sys.exit(1)

    polygon = 'POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))' % (bbox[0], bbox[1], bbox[0], bbox[3], bbox[2], bbox[3], bbox[2], bbox[1], bbox[0], bbox[1])

    sql = "select filename from %s where geom && st_setsrid('%s'::geometry, 4326)" % ( table, polygon )
    cur.execute( sql )
    rows = cur.fetchall()

    if len(rows) == 0: return []

    files = []

    for row in rows:
        filename = row[0]
        name = filename[:26] + '.tif'
        subdir = filename[2:7]
        f = os.path.join( DOQQS, subdir, name )
        files.append(f)

    return files



def getStatesCountiesFromBbox( cur, bbox ):

    polygon = 'POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))' % (bbox[0], bbox[1], bbox[0], bbox[3], bbox[2], bbox[3], bbox[2], bbox[1], bbox[0], bbox[1])

    try:
        conn = psycopg2.connect( CONFIG['dsn'] )
    except:
        print "ERROR: failed to connect to database!"
        sys.exit(1)

    cur = conn.cursor()

    sql = "select geoid from census.county where geom && st_setsrid('%s'::geometry, 4326)" % ( polygon )
    cur.execute( sql )

    states = []
    counties = []
    for row in cur:
        states.append( row[0][:2] )
        counties.append( row[0] )

    states = unique(states)
    counties = unique(counties)

    return (states, counties)


def loadZippedShape( table, path, re_zipfile ):
    # create a tmp dir
    tmp = os.path.join( CONFIG.get('tmpdir', path), 'tmp-'+str(os.getpid()) )
    if not os.path.exists( tmp ):
        os.makedirs(tmp)

    verbose = CONFIG.get('verbose', False)

    dsn = 'PG:' + CONFIG['dsn'] + ' active_schema=census'

    ogr_opts = ['-overwrite', '-lco', 'OVERWRITE=YES', '-lco', 'PRECISION=NO',
                '-lco', 'GEOMETRY_NAME=geom', '-lco', 'FID=gid']

    # gdal/ogr 1.10 does not drop the tables with -overwrite
    # so we will do it like this.
    conn, cur = getDatabase()
    cur.execute( 'drop table if exists %s cascade' % ( table ) )
    conn.commit()
    conn.close()

    first = True
    for root, dirs, files in os.walk( path ):
        for f in files:
            if not re.match( re_zipfile, f ): continue

            # unzip it to tmp
            cmd = ['unzip', '-q', '-d', tmp, '-j', os.path.join( root, f )]
            if verbose:
                print ' '.join( cmd )
            subprocess.call( cmd )

            for root2, dirs2, files2 in os.walk( tmp ):
                for shpfile in files2:
                    if not re.match( r'.*.shp$', shpfile ): continue
                    # ogr2ogr to load it
                    cmd = ['ogr2ogr', '-t_srs', 'EPSG:4326', '-nln', table,
                           '-nlt', 'PROMOTE_TO_MULTI',
                           '-f', 'PostgreSQL'] + ogr_opts + \
                           [ dsn, os.path.join( root2, shpfile) ]
                    if verbose:
                        print ' '.join( cmd )
                    subprocess.call( cmd )
                    if first:
                        first = False
                        ogr_opts = [ '-append' ]

            # remove files in tmp
            for root2, dirs2, files2 in os.walk( tmp ):
                for f2 in files2:
                    os.remove( os.path.join( root2, f2 ) )

    # remove tmp dir
    os.rmdir( tmp )


