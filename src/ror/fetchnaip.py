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
import getopt
import subprocess
from config import *
from utils import getDatabase, loadZippedShape
from status import *



def getLoadNaipShp(year, allStates):
    verbose = CONFIG.get('verbose', False)

    # get the template url
    urltpl = CONFIG['naip.url']['shp.url']

    # get values for the fields in the template
    yy = year[-2:]
    if allStates:
        states = FIPS2ST.values()
    else:
        states = [FIPS2ST[CONFIG['areaOfInterest'][:2]]]

    # define where the files will get put
    shp = CONFIG['naip.shapefile']
    shpdir = os.path.join(CONFIG['projectHomeDir'], shp, year)
    print 'shpdir:', shpdir
    if not os.path.exists( shpdir ):
        os.makedirs( shpdir )

    # loop through the list of states and fetch the files
    for st in states:
        url = urltpl.format(year, st, yy)
        print 'getLoadNaipShp:', url
        cmd = ['wget', '-o', shpdir + 'shapes.log',
               '-N', '-nv', '-nd', '-nH', '-P', shpdir, url]

        if verbose:
            print ' '.join(cmd)
        subprocess.call( cmd )

    zipfile = r'.*\.zip$'
    table = CONFIG.get('naip.shptable', 'naip.naipbbox{0}')
    loadZippedShape( table.format(year), shpdir, zipfile )




def getNaipFiles(year, areaOfInterest, donaip):
    verbose = CONFIG.get('verbose', False)

    home = CONFIG['projectHomeDir']
    doqqs = CONFIG['naip.download']
    doqqDir = os.path.join( home, doqqs, year )
    if not os.path.exists(doqqDir):
        os.makedirs(doqqDir)

    conn, cur = getDatabase()

    # template url for fething files
    try:
        template = CONFIG['naip.url']['doqq.urls'][year]
    except:
        template = ''

    if template == '':
        print 'ERROR: CONFIG[naip.url][doqq.urls][%] is not configured!' % (year)
        conn.close()
        return True

    # create table if not exists to log downloaded DOQQs
    sql = '''create table if not exists naip.naipfetched{} (
        gid integer not null primary key,
        processed boolean)'''.format(year)
    cur.execute( sql )

    # use default areaOfInterest in CONFIG
    if len(areaOfInterest) == 0:
        areaOfInterest = CONFIG['areaOfInterest']

    # analyze areaOfInterest to see if its a fips code or bbox
    if re.match(r'^[0-9]+$', areaOfInterest):
        if len(areaOfInterest) == 2: # we have a useful state code
            st = FIPS2ST[areaOfInterest].upper()
            join = ''
            where = " a.st='%s'" % (st)
        elif len(areaOfInterest) == 5: # we have a useful county code
            join = ' join county c on st_intersects(a.geom, c.geom) '
            where = " c.geoid = '%s' " % (areaOfInterest)
        elif len(areaOfInterest) == 10: # we have a cousub code
            join = ' join cousub c on st_intersects(a.geom, c.geom) '
            where = " c.geoid = '%s' " % (areaOfInterest)
        else: # not sure what we have
            print "ERROR: Area of interest is not understood (%s)!" % areaOfInterest
            conn.close()
            return True

        sql = '''select count(*)
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            {1}
            where b.gid is null and {2}
            '''.format(year, join, where)
        cur.execute(sql)
        count = cur.fetchone()[0]

        sql = '''select a.gid, filename
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            {1}
            where b.gid is null and {2}
            '''.format(year, join, where)

    elif re.match(r'^(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*)$', areaOfInterest):
        bbox = areaOfInterest.split(',')

        # query to get list of doqqs to fetch
        sql = '''select count(*)
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            where b.gid is null
            and 'LINESTRING({1} {2},{3} {4})'::geometry && a.geom'''.format(year, bbox[0], bbox[1], bbox[2], bbox[3])
        cur.execute(sql)
        count = cur.fetchone()[0]

        sql = '''select a.gid, filename
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            where b.gid is null
            and 'LINESTRING({1} {2},{3} {4})'::geometry && a.geom'''.format(year, bbox[0], bbox[1], bbox[2], bbox[3])

    else:
        print "ERROR: Area of interest is not understood (%s)!" % areaOfInterest
        conn.close()
        return True

    print 'Plan is to download {} DOQQs'.format(count)

    if donaip:
        if verbose:
            print sql

        cur.execute( sql )

        # get a 2nd cur for updating table
        cur2 = conn.cursor()

        sql = "insert into naipfetched{0} values ({1}) on conflict do nothing"

        # loop through list and download them
        for row in cur:
            # fetch the file
            filename = row[1]
            sdir = filename[2:7]
            name = filename[:26] + '.tif'
            url = template.format(sdir, name)
            outdir = os.path.join( doqqDir, sdir )
            if not os.path.exists( outdir ):
                os.makedirs( outdir )
            log = os.path.join( home, doqqs, 'doqqs-{}.log'.format(year))
            cmd = ['wget', '-a', log,
                   '-N', '-nv', '-nd', '-nH', '-P', outdir, url]
            if verbose:
                print ' '.join( cmd )
            subprocess.call( cmd )

            # mark it as downloaded
            cur2.execute( sql.format(year, row[0]) )

    conn.commit()
    conn.close()

    return False



def FetchNaip( argv ):
    try:
        opts, args = getopt.getopt(argv, "y:a:", ['no-shp', 'no-naip', 'status', 'area'])
    except:
        return True # error occurred

    year = CONFIG['year']
    doshp = True
    donaip = True
    dostatus = False
    allStates = False
    areaOfInterest = ''

    for opt, arg in opts:
        if opt == '-y':
            year = arg
        elif opt == '--all-states':
            allStates = True
        elif opt == '--no-shp':
            doshp = False
        elif opt == '--no-naip':
            donaip = False
        elif opt == '--status':
            dostatus = True
        elif opt in ('-a', '--area'):
            areaOfInterest = arg

    if dostatus:
        reportStatus('naip', {'year':year})
        return False

    if doshp:
        if getLoadNaipShp(year, allStates):
            print "WARNING: getLoadNaipShp got error(s)!"

    if getNaipFiles(year, areaOfInterest, donaip):
        print "WARNING: getNaipFiles got error(s)!"

    return False # no errors


