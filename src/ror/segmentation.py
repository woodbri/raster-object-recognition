
import os
import sys
import glob
import re
import getopt
from osgeo import ogr

from utils import getDatabase, runCommand
from polygonstats import PolygonStats, addShapefileStats
import otbApplication
from config import *

# this probably will not work on Windows, except in the docker env.
otbpath = os.environ.get('OTB_APPLICATION_PATH', None)
if otbpath is None:
    os.environ['OTB_APPLICATION_PATH']='/usr/lib/otb/applications/'


def getDoqqsForArea( year, areaOfInterest ):
    verbose = CONFIG.get('verbose', False)

    home = CONFIG['projectHomeDir']
    doqqs = CONFIG['naip.doqq_dir']
    doqqDir = os.path.join( home, doqqs, year )

    conn, cur = getDatabase()

    # use default areaOfInterest in CONFIG
    if len(areaOfInterest) == 0:
        areaOfInterest = CONFIG['areaOfInterest']

    # analyze areaOfInterest to see if its a fips code or bbox
    if re.match(r'^[0-9]+$', areaOfInterest):
        if len(areaOfInterest) == 2: # we have a useful state code
            st = FIPS2ST[areaOfInterest].upper()
            join = ''
            where = " a.st='{}'".format(st)
        elif len(areaOfInterest) == 5: # we have a useful county code
            join = ' join county c on st_intersects(a.geom, c.geom) '
            where = " c.geoid = '{}' ".format(areaOfInterest)
        elif len(areaOfInterest) == 10: # we have a cousub code
            join = ' join cousub c on st_intersects(a.geom, c.geom) '
            where = " c.geoid = '{}' ".format(areaOfInterest)
        else: # not sure what we have
            print "ERROR: Area of interest is not understood ({})!".format(areaOfInterest)
            conn.close()
            sys.exit(1)

        sql = '''select a.gid, filename
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            {1}
            where b.gid is not null and {2}
            '''.format(year, join, where)

    elif re.match(r'^(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*),(-?[0-9]+\.?[0-9]*)$', areaOfInterest):
        bbox = areaOfInterest.split(',')

        sql = '''select a.gid, filename
            from naipbbox{0} a
            left outer join naipfetched{0} b on a.gid=b.gid
            where b.gid is not null
            and 'LINESTRING({1} {2},{3} {4})'::geometry && a.geom'''.format(year, bbox[0], bbox[1], bbox[2], bbox[3])

    else:
        print "ERROR: Area of interest is not understood ({})!".format(areaOfInterest)
        conn.close()
        return True

    if verbose:
        print sql
    cur.execute( sql )

    files = []
    for row in cur:
        filename = row[1]
        sdir = filename[2:7]
        name = filename[:26] + '.tif'
        files.append( os.path.join( doqqDir, sdir, name ) )

    conn.close()

    if len(files) == 0:
        print "No files were found to process your request!"
        sys.exit(1)

    return files


def createVrtForAOI( fvrt, year, area ):
    verbose = CONFIG.get('verbose', False)

    # temp file to write doqqs into
    fvrtin = fvrt + '.in'

    # get a list of doqqs the intersect our area of interest
    # and write them to a temp file
    files = getDoqqsForArea( year, area )
    fh = open( fvrtin, 'wb' )
    for f in files:
        fh.write( f + "\n" )
    fh.close()

    cmd = ['gdalbuildvrt', '-input_file_list', fvrtin, fvrt]
    runCommand(cmd, verbose)


def smoothing(fin, fout, foutpos, spatialr, ranger, rangeramp, thres, maxiter, ram):
    app = otbApplication.Registry.CreateApplication('MeanShiftSmoothing')
    app.SetParameterString('in', fin)
    app.SetParameterString('fout', fout)
    app.SetParameterString('foutpos', foutpos)
    app.SetParameterInt('spatialr', spatialr)
    app.SetParameterFloat('ranger', ranger)
    app.SetParameterFloat('rangeramp', rangeramp)
    app.SetParameterFloat('thres', thres)
    app.SetParameterInt('maxiter', maxiter)
    app.SetParameterInt('ram', ram)
    app.SetParameterInt('modesearch', 0)
    app.ExecuteAndWriteOutput()


def segmentit(fin, finpos, fout, spatialr, ranger, tilesize, tmpdir):
    debug = CONFIG.get('debug', False)

    app = otbApplication.Registry.CreateApplication('LSMSSegmentation')
    app.SetParameterString('in', fin)
    app.SetParameterString('inpos', finpos)
    app.SetParameterString('out', fout)
    app.SetParameterString('tmpdir', tmpdir)
    app.SetParameterInt('spatialr', spatialr)
    app.SetParameterFloat('ranger', ranger)
    app.SetParameterInt('minsize', 0)
    app.SetParameterInt('tilesizex', tilesize)
    app.SetParameterInt('tilesizey', tilesize)
    app.SetParameterInt('cleanup', 1 if debug else 0)
    app.ExecuteAndWriteOutput()


def mergesmall(fin, finseg, fout, minsize, tilesize):
    app = otbApplication.Registry.CreateApplication('LSMSSmallRegionsMerging')
    app.SetParameterString('in', fin)
    app.SetParameterString('inseg', finseg)
    app.SetParameterString('out', fout)
    app.SetParameterInt('minsize', minsize)
    app.SetParameterInt('tilesizex', tilesize)
    app.SetParameterInt('tilesizey', tilesize)
    app.ExecuteAndWriteOutput()


def vectorize(fin, finseg, fout, tilesize):
    app = otbApplication.Registry.CreateApplication('LSMSVectorization')
    app.SetParameterString('in', fin)
    app.SetParameterString('inseg', finseg)
    app.SetParameterString('out', fout)
    app.SetParameterInt('tilesizex', tilesize)
    app.SetParameterInt('tilesizey', tilesize)
    app.ExecuteAndWriteOutput()


def loadsegments(fsegshp, year, job):

    verbose = CONFIG.get('verbose', False)
    epsg = CONFIG.get('naip.projection', 'EPSG:4326')
    dsn = 'PG:' + CONFIG['dsn']

    table = CONFIG.get('seg.table', 'segments.y{0}_{1}').format(year, job)
    conn, cur = getDatabase()

    sql = 'drop table if exists {} cascade'.format(table)
    if verbose:
        print sql
    cur.execute( sql )
    conn.commit()
    conn.close()

    cmd = ['ogr2ogr', '-t_srs', epsg, '-nln', table,
           '-overwrite', '-lco', 'OVERWRITE=YES', '-lco', 'PRECISION=NO',
           '-lco', 'GEOMETRY_NAME=geom', '-lco', 'FID=gid', '-f', 'PostgreSQL',
           dsn, fsegshp]
    runCommand(cmd, verbose)


def Usage():
    print '''
Usage: ror_cli segment options
    [-a|--area fips|bbox]   - only process this fips area or
                              xmin,ymin,xmax,ymax bbox area
    [-y|--year yyyy]        - select year to process
    [-s|--spatialr int]     - spatial radius of neigborhood in pixels
    [-r|--ranger float]     - radiometric radius in multi-spectral space
    [-t|--thresh float]     - convergence threshold
    [-p|--rangeramp float]  - range radius coefficient where:
                              y = rangeramp*x+ranger
    [-i|--max-iter int]     - max interation during convergence
    [-m|--minsize int]      - minimum segment size in pixels
    [-T|--tilesize int]     - size of tiles in pixels
    [-R|--ram int(MB)]      - available ram for processing
    [-j|--job name]         - unique job name, will be used to
                              to create table to store segments in
    '''
    sys.exit(2)


def Segmentation( argv ):

    try:
        opts, args = getopt.getopt(argv, 'ha:y:s:r:t:i:p:m:T:R:j:',
            ['help', 'area', 'year', 'spatialr', 'ranger', 'thresh',
             'max-iter', 'rangeramp', 'minsize', 'tilesize', 'ram', 'job'])
    except getopt.GetoptError:
        print 'ERROR in Segmentation options!'
        print 'args:', argv
        print getopt.GetoptError
        return True

    verbose   = CONFIG.get('verbose', False)
    # table name template, where {0}= year, {1}= jobname
    table     = CONFIG.get('seg.table', 'segments.y{0}_{1}')

    area      = CONFIG.get('areaOfInterest', None)
    year      = CONFIG.get('year', None)
    spatialr  = CONFIG.get('seg.spatialr', None)
    ranger    = CONFIG.get('seg.ranger', None)
    thresh    = CONFIG.get('seg.thresh', None)
    rangeramp = CONFIG.get('seg.rangeramp', None)
    maxiter   = CONFIG.get('seg.max-iter', None)
    minsize   = CONFIG.get('seg.minsize', None)
    tilesize  = CONFIG.get('seg.tilesize', None)
    ram       = CONFIG.get('seg.ram', None)
    job       = None

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            Usage()
        elif opt in ('-a', '--area'):
            area = arg
        elif opt in ('-y', '--year'):
            year = str(int(arg))
        elif opt in ('-s', '--spatialr'):
            spatialr = int(arg)
        elif opt in ('-r', '--ranger'):
            ranger = float(arg)
        elif opt in ('-t', '--thresh'):
            thresh = float(arg)
        elif opt in ('-p', '--rangeramp'):
            rangeramp = float(arg)
        elif opt in ('-i', '--max-iter'):
            maxiter = int(arg)
        elif opt in ('-m', '--minsize'):
            minsize = int(arg)
        elif opt in ('-T', '--tilesize'):
            tilesize = int(arg)
        elif opt in ('-R', '--ram'):
            ram = int(arg)
        elif opt in ('-j', '--job'):
            job = arg

    # check all args are defined
    chkargs = {'area':area, 'year':year, 'spatialr':spatialr, 'ranger':ranger,
               'thresh':thresh, 'rangeramp':rangeramp, 'max-iter':maxiter,
               'minsize':minsize, 'tilesize':tilesize, 'ram':ram, 'job':job}
    err = False
    for k in chkargs:
        if chkargs[k] is None:
            err = True
            print "ERROR: '{}' is not defined!".format(k)
    if err:
        print "Please define them in the config file or as args!"
        Usage()

    # generate tmp filenames for LSMS process
    pid        = str(os.getpid())
    home       = CONFIG['projectHomeDir']
    tmpdirs    = CONFIG.get('tmpdirs', [os.path.join(home, 'tmp')])
    tmpdir     = tmpdirs[0]
    vrtin      = os.path.join(tmpdir, 'tmp-{}-areaofinterest.vrt'.format(pid))
    fsmooth    = os.path.join(tmpdir, 'tmp-{}-smooth.tif'.format(pid))
    fsmoothpos = os.path.join(tmpdir, 'tmp-{}-smoothpos.tif'.format(pid))
    fsegs      = os.path.join(tmpdir, 'tmp-{}-segs.tif'.format(pid))
    fmerged    = os.path.join(tmpdir, 'tmp-{}-merged.tif'.format(pid))
    fsegshp    = os.path.join(home, 'data', 'year' 'segments', 'segments-{}.shp'.format(job))

    # TODO add timing stats

    # get a vrt file defining the area of interest
    createVrtForAOI( vrtin, year, area )

    print 'Starting smoothing ...'
    smoothing(vrtin, fsmooth, fsmoothpos, spatialr, ranger, rangeramp, thresh, maxiter, ram)

    print 'Starting Segmentation ...'
    segmentit(fsmooth, fsmoothpos, fsegs, spatialr, ranger, tilesize, tmpdir)

    print 'Starting small area merging ...'
    mergesmall(fsmooth, fsegs, fmerged, minsize, tilesize)
    
    print 'Starting vectorization of segments ...'
    vectorize(fsmooth, fmerged, fsegshp, tilesize)

    print 'Adding stats to vectors ...'
    addShapefileStats(fsegshp)

    print 'Loading segments into database ...'
    loadsegments(fsegshp, year, job)

    print 'Cleanning up tmp files ...'
    # TODO add parameter to not do this?

    print 'Done!'

if __name__ == '__main__':
    if len(sys.argv) == 1:
        Usage()

    Segmentation(sys.argv[1:])
