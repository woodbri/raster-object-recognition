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
import glob
import re
import getopt
from osgeo import gdal, ogr

from utils import getDatabase, runCommand
from polygonstats import PolygonStats, addShapefileStats
from optimalparameters import getOptimalParameters
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


def UsageOP():
    print '''
Usage: ror_cli optimal-params options
    [-l|--latlog lat,lon]   - center location to use
    [-s|--size 512]         - pixel size of window to check default: 512
    [-a|--area bbox]        - small bbox of area to check
    [-i|--isboxy 1|0]       - are objects square|rectangle or not
    [-b|--bands 0,1,2,4]    - which bands to use, zero based numbers
                              default: 0,1,2,4  (R,G,B,IR)
    [-y|--year YYYY]        - select year to process
    [-p|--plots]            - show graph plots of data
    [-v|--verbose]          - print debug info
    [-h|--help]
    '''
    sys.exit(2)



def OptimalParams( argv ):
    try:
        opts, args = getopt.getopt(argv, "l:s:a:i:b:y:pvh",
            ['latlon', 'size', 'area', 'isboxy', 'bands', 'year',
             'plots', 'verbose', 'help', 'debug'])
    except getopt.GetoptError:
        print 'ERROR in optimal-params options!'
        print 'args:', argv
        print getopt.GetoptError
        return True

    verbose   = CONFIG.get('verbose', False)
    area      = CONFIG.get('areaOfInterest', None)
    year      = CONFIG.get('year', None)
    latlon    = None
    size      = 512
    boxy      = True
    bands     = [0,1,2,4]
    plotit    = False
    debug     = False
    error     = False

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            UsageOP()
        elif opt in ('-a', '--area'):
            area = arg
        elif opt in ('-y', '--year'):
            year = str(int(arg))
        elif opt in ('-x', '--isboxy'):
            boxy = bool(arg)
        elif opt in ('-b', '--bands'):
            bands = [int(i) for i in arg.split(',')]
        elif opt in ('-l', '--latlon'):
            latlon = [float(i) for i in arg.split(',')]
            print 'latlon:', latlon
        elif opt in ('-s', '--size'):
            if int(arg) > 0:
                size = int(arg)
            else:
                print "\nERROR: argument size must be > 0 !"
                error = True
        elif opt in ('-p', '--plot', '--plots'):
            plotit = True
        elif opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('--debug'):
            debug = True

    if year is None:
        print "\nERROR: year is not defined!"
        error = True

    if area is None and latlon is None:
        print "\nERROR: either area or latlon must be defined!"
        error = True

    if error:
        return True

    print 'verbose:', verbose
    print 'debug:', debug

    pid        = str(os.getpid())
    home       = CONFIG['projectHomeDir']
    tmpdirs    = CONFIG.get('tmpdirs', [os.path.join(home, 'tmp')])
    tmpdir     = tmpdirs[0]
    vrtin      = os.path.join(tmpdir, 'tmp-{}-areaofinterest.vrt'.format(pid))
    foptimal   = os.path.join(tmpdir, 'tmp-{}-optimal.tif'.format(pid))

    # if latlon then set area to bbox based on 1 meter/pixel
    # and double that to make sure with have some extra
    if not latlon is None:
        dsize = size / 111120.0
        xmin = latlon[1] - dsize
        xmax = latlon[1] + dsize
        ymin = latlon[0] - dsize
        ymax = latlon[0] + dsize
        area = "{0:.6f},{1:.6f},{2:.6f},{3:.6f}".format(xmin,ymin,xmax,ymax)
        if debug:
            print 'dsize:', dsize
            print 'latlon:', latlon

    if debug:
        print 'area:', area

    # get a vrt file defining the area of interest
    createVrtForAOI( vrtin, year, area )

    ds = gdal.Open( vrtin )
    gt = ds.GetGeoTransform()
    '''
    gt[0] = originX
    gt[1] = pixelWdith
    gt[2] = 0
    gt[3] = originY
    gt[4] = 0
    gt[5] = pixelHeight
    '''
    width = ds.RasterXSize
    height = ds.RasterYSize
    if min(width, height) < size:
        size = min(width, height)

    xoff = str(int((latlon[1] - gt[0]) / gt[1] - size/2))
    yoff = str(int((latlon[0] - gt[3]) / gt[5]  - size/2))
    size = str(int(size))
    cmd = ['gdal_translate', '-of', 'GTiff', '-srcwin', xoff, yoff,
           size, size, vrtin, foptimal]
    runCommand( cmd, verbose )

    opt = getOptimalParameters( boxy, foptimal, bands, verbose, False )

    ds = None
    if debug:
        print "Leaving tmp files for {}".format( vrtin )
    else:
        print "Removing tmp files."
        os.remove( vrtin )
        if os.path.exists( vrtin + '.in' ):
            os.remove( vrtin + '.in' )
        os.remove( foptimal )
        if os.path.exists( foptimal + '.aux.xml' ):
            os.remove( foptimal + '.aux.xml' )
        if os.path.exists( foptimal + '.msk' ):
            os.remove( foptimal + '.msk' )

    print "   Optimal Parameters    "
    print "    |  Hs  |  Hr  |   M  "
    print "----+------+------+------"
    print "min |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_min'], opt['hr_min'], opt['M_min'])
    print "max |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_max'], opt['hr_max'], opt['M_max'])
    print "avg |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_avg'], opt['hr_avg'], opt['M_avg'])
    print "----+------+------+------"

    return False



def Usage():
    print '''
Usage: ror_cli segment options
    [-a|--area fips|bbox]   - only process this fips area or
                              xmin,ymin,xmax,ymax bbox area
    [-y|--year yyyy]        - select year to process
    [-o|--optimal min|max|avg] - compute the optimal parameters and
                              use them instead of -s, -r, -m
                              select if you want the min, max, or avg
                              of the computed values
       [-x|--isboxy 0|1]    - are objects boxy, used with --optimal
       [-b|--bands 0,1,2,4] - which bands to use, used iwth --optimal
    [-s|--spatialr int]     - spatial radius of neigborhood in pixels
    [-r|--ranger float]     - radiometric radius in multi-spectral space
    [-m|--minsize int]      - minimum segment size in pixels
    [-t|--thresh float]     - convergence threshold
    [-p|--rangeramp float]  - range radius coefficient where:
                              y = rangeramp*x+ranger
    [-i|--max-iter int]     - max interation during convergence
    [-T|--tilesize int]     - size of tiles in pixels
    [-R|--ram int(MB)]      - available ram for processing
    [-j|--job name]         - unique job name, will be used to
                              to create table to store segments in
    NOTE: --optimal will take a 1024x1024 image located at the center
          of --area to compute the optimal parameters. If you want more
          control over where the the sample is selected, use option
          optimal-params above and set -s, -r, -m explicitly
    '''
    sys.exit(2)


def Segmentation( argv ):

    try:
        opts, args = getopt.getopt(argv, 'ha:y:s:r:t:i:p:m:T:R:j:o:x:b:',
            ['help', 'area', 'year', 'spatialr', 'ranger', 'thresh',
             'max-iter', 'rangeramp', 'minsize', 'tilesize', 'ram', 'job',
             'optimal', 'boxy', 'bands', 'debug'])
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
    optimal   = None
    boxy      = True
    bands     = [0,1,2,4]
    debug     = False

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            Usage()
        elif opt in ('-a', '--area'):
            area = arg
        elif opt in ('-y', '--year'):
            year = str(int(arg))
        elif opt in ('-o', '--optimal'):
            if arg in ('min', 'max', 'avg'):
                optimal = arg
            else:
                print "\nERROR: -o|--optimal must take value of min|max|avg!"
                Usage()
        elif opt in ('-x', '--isboxy'):
            boxy = bool(arg)
        elif opt in ('-b', '--bands'):
            bands = [int(i) for i in arg.split(',')]
        elif opt in ('-s', '--spatialr'):
            spatialr = int(arg)
        elif opt in ('-r', '--ranger'):
            ranger = float(arg)
        elif opt in ('-m', '--minsize'):
            minsize = int(arg)
        elif opt in ('-t', '--thresh'):
            thresh = float(arg)
        elif opt in ('-p', '--rangeramp'):
            rangeramp = float(arg)
        elif opt in ('-i', '--max-iter'):
            maxiter = int(arg)
        elif opt in ('-T', '--tilesize'):
            tilesize = int(arg)
        elif opt in ('-R', '--ram'):
            ram = int(arg)
        elif opt in ('-j', '--job'):
            job = arg
        elif opt in ('--debug'):
            debug = True

    # check all args are defined
    chkargs = {'area':area, 'year':year, 'thresh':thresh,
               'rangeramp':rangeramp, 'max-iter':maxiter,
               'tilesize':tilesize, 'ram':ram, 'job':job}
    err = False
    for k in chkargs:
        if chkargs[k] is None:
            err = True
            print "ERROR: '{}' is not defined!".format(k)

    if optimal is None:
        chkargs = {'spatialr':spatialr, 'ranger':ranger, 'minsize':minsize}
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
    foptimal   = os.path.join(tmpdir, 'tmp-{}-optimal.tif'.format(pid))
    fsegshp    = os.path.join(home, 'data', 'year' 'segments', 'segments-{}.shp'.format(job))

    # TODO add timing stats

    # get a vrt file defining the area of interest
    createVrtForAOI( vrtin, year, area )

    if not optimal is None:
        ds = gdal.Open( vrtin )
        width = ds.RasterXSize
        height = ds.RasterYSize
        size = 1024
        if min(width, height) < size:
            size = min(width, height)

        xoff = str(int(width/2 - size/2))
        yoff = str(int(height/2 - size/2))
        size = str(int(size))
        cmd = ['gdal_translate', '-of', 'GTiff', '-srcwin', xoff, yoff,
               size, size, vrtin, foptimal]
        runCommand( cmd, verbose )

        optParams = getOptimalParameters( boxy, foptimal, bands, verbose, False )
        spatialr = optParams['hs_' + optimal]
        ranger   = optParams['hr_' + optimal]
        minsize  = optParams['M_'  + optimal]

        ds = None
        if not Debug:
            of.remove( foptimal )

    if verbose:
        print "Using segmentation parameters:"
        print "  spatialr (hs): {}".format(spatialr)
        print "  ranger   (hr): {}".format(ranger)
        print "  minsize   (M): {}".format(minsize)

    sys.exit(0)

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

    if debug:
        print 'Leaving tmp files in {}.'.format(tmpdir)
    else:
        print 'Cleanning up tmp files ...'
        os.remove( vrtin )
        os.remove( fsmooth )
        os.remove( fsmoothpos )
        os.remove( fsegs )
        os.remove( fmerged )
        os.remove( fsegshp )

    print 'Done!'

if __name__ == '__main__':
    if len(sys.argv) == 1:
        Usage()

    Segmentation(sys.argv[1:])

