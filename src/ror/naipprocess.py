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
import getopt
import glob
import psycopg2
from osgeo import gdal
import subprocess
from multiprocessing import Process, cpu_count
from config import *
from utils import getDatabase, runCommand



def createVRT(vrtfile, bands):
    
    ds = gdal.Open( bands[0][0] )
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize
    gt = ds.GetGeoTransform()
    srs = ds.GetProjectionRef()
    ds = None

    vrt = '''<VRTDataset rasterXSize="{0}" rasterYSize="{1}">
    <SRS>{2}</SRS>
    <GeoTransform>{3:.15f}, {4:.15f}, {5:.15f}, {6:.15f}, {7:.15f}, {8:.15f}</GeoTransform>'''\
      .format(xsize, ysize, gdal.EscapeString(srs, scheme = gdal.CPLES_XML), \
      gt[0], gt[1], gt[2], gt[3], gt[4], gt[5])

    dstBand = 1
    for b in bands:
        # open file and get info from it
        ds = gdal.Open( b[0] )
        dataType = ds.GetRasterBand(b[1]).DataType
        dataTypeName = gdal.GetDataTypeName(dataType)
        ds = None

        # add this band to the vrt
        vrt = vrt + '''
          <VRTRasterBand dataType="{0}" band="{1:d}">
            <ColorInterp>{2}</ColorInterp>
            <SimpleSource>
            <SourceFilename relativeToVRT="1">{3}</SourceFilename>
            <SourceBand>{4:d}</SourceBand>
            <SrcRect xOff="0" yOff="0" xSize="{5:d}" ySize="{6:d}"/>
            <DstRect xOff="0" yOff="0" xSize="{5:d}" ySize="{6:d}"/>
            </SimpleSource>
          </VRTRasterBand>'''.format( \
            dataTypeName, dstBand, b[2], b[0], b[1], \
            xsize, ysize)
        dstBand = dstBand + 1

    vrt = vrt + '''
</VRTDataset>'''

    # create an in memory VRT file from the XML
    vrt_ds = gdal.Open( vrt )
    # and copy it to a file
    driver = gdal.GetDriverByName('VRT')
    dst_ds = driver.CreateCopy( vrtfile, vrt_ds )

    dst_ds = None

        

def processDOQQ(row, procn, year):

    outSrs = CONFIG.get('naip.projection', 'EPSG:4326')

    # setup out paths
    verbose = CONFIG.get('verbose', False)
    home = CONFIG['projectHomeDir']
    downl = CONFIG['naip.download']
    doqqs = CONFIG['naip.doqq_dir']
    d_source = os.path.join( home, downl, year )
    d_target = os.path.join( home, doqqs, year )

    # each proc rotates through the tmpdirs if multiple defined
    tmpdirs = CONFIG.get('tmpdirs', [os.path.join(home, 'tmp')])
    tmpdir = tmpdirs[procn%len(tmpdirs)]

    # make sure the tmpdir path exists
    try:
        if not os.path.exists(tmpdir):
            os.makedirs(tmpdir)
    except:
        pass

    filename = row[0]
    name = filename[:26] + '.tif'
    subdir = filename[2:7]
    f_source = os.path.join(d_source, subdir, name)
    f_target = os.path.join(d_target, subdir, name)
    if not os.path.exists( f_source ):
        print "WARNING: {} does not exist!".format( filepath )
        return False

    # make sure the target path exists
    try:
        if not os.path.exists( os.path.split(f_target)[0] ):
            os.makedirs( os.path.split(f_target)[0] )
    except:
        pass

    tempfile1 = os.path.join(tmpdir, str(os.getpid()) + '-1-' + name)
    tempfile2 = os.path.join(tmpdir, str(os.getpid()) + '-2-' + name)

    '''
    # I don't think we have collars so lets not do this now
    # we can add it back later if needed.

    # clean up collars
    cmd = ['nearblack', '-co', 'TILED=YES', '-of', 'GTiff', '-nb', '0',
           '-near', '0', '-setmask', '-q', tempfile1, f_source]
    runCommand( cmd, verbose )
    '''

    # gdalwarp source file to outSrs
    cmd = ['gdalwarp', '-t_srs', outSrs, '-dstalpha', '-co', 'TILED=YES',
           f_source, tempfile1]
    runCommand( cmd, verbose )

    vrtfile = tempfile2.replace('.tif', '.vrt')
    bands = [ [tempfile1, 1, 'Red'],
              [tempfile1, 2, 'Green'],
              [tempfile1, 3, 'Blue'],
              [tempfile1, 5, 'Alpha'],  # Alpha band
              [tempfile1, 4, 'Gray'],   # IR band
            ]
        
    createVRT( vrtfile, bands )
    mask = 4

    if verbose:
        print "vrtfile:", vrtfile, "f_target:", f_target

    # gdal_translate jpeg compress it to target
    cmd = ['gdal_translate', '-co', 'TILED=YES', '-co', 'JPEG_QUALITY=90',
           '-co', 'COMPRESS=JPEG', '-co', 'INTERLEAVE=BAND',
           # '-mask', str(mask), '-co', 'ALPHA=YES',
           '-mask', str(mask),
           '--config', 'GDAL_TIFF_INTERNAL_MASK', 'YES', vrtfile, f_target]
    runCommand( cmd, verbose )

    # gdaladdo to target
    cmd = ['gdaladdo', '-clean', '-r', 'average', f_target,
           '2', '4', '8', '16', '32', '64', '128']
    runCommand( cmd, verbose )

    # remove tmpfiles
    rmglob = os.path.join(tmpdir, str(os.getpid()) + '*')
    if verbose:
        print "rm {}".format( rmglob )

    if True:
        for f in glob.glob( rmglob ):
            os.remove( f )

    return True



def processNaipFromQuery(nproc, procn, limit, year):
    conn, cur = getDatabase()
    verbose = CONFIG.get('verbose', False)

    clause = ''
    if nproc > 1:
        clause = " and a.gid % {0} = {1} ".format(nproc, procn)

    clause2 = ''
    if limit > 0:
        clause2 = " limit {0} ".format(limit)

    sql = """select filename, a.gid
        from naipbbox{0} a
        left outer join naipfetched{0} b on a.gid=b.gid
        where b.gid is not null and b.processed is null
        {1}
        order by a.gid
        {2}
        """.format(year, clause, clause2)

    if verbose:
        print 'proc: {}, sql: {}'.format(procn, sql)

    cur.execute( sql )
    rows = cur.fetchall()

    if verbose:
        print 'proc: {}, count: {}'.format(procn, len(rows))

    for row in rows:
        if processDOQQ( row, procn, year ):
            sql = 'update naipfetched{0} set processed=true where gid={1}'.format(year, row[1])
            cur.execute( sql )

    conn.commit()
    conn.close()



def processNaipFromList(files, procn, year):
    conn, cur = getDatabase()
    table = CONFIG['naip.shptable'].format(year)

    for f in files:
        parts = os.path.split(f)              # "path", "file"
        fname = os.path.splitext(parts[1])[0] # "file", "ext"
        # look up file in database to get its gid
        sql = """select filename, gid from {0}
                 where filename like '{1}%'""".format(table, fname)

        cur.execute( sql )
        rows = cur.fetchall()

        for row in rows:
            if processDOQQ( row, procn, year ):
                sql = 'update naipfetched{0} set processed=true where gid={1}'.format(year, row[1])
                cur.execute( sql )

    conn.commit()
    conn.close()



def ProcessNaip( argv ):
    try:
        opts, args = getopt.getopt(argv, "y:n:l:f", ['year', 'nproc', 'limit', 'files'])
    except:
        return True # error occurred

    verbose = CONFIG.get('verbose', False)
    year = CONFIG['year']
    nproc = CONFIG.get('nproc', 1)
    limit = 0
    dofiles = False

    for opt, arg in opts:
        if opt in ('-y', '--year'):
            year = arg
        elif opt in ('-n', '--nproc'):
            nproc = int(arg)
        elif opt in ('-l', '--limit'):
            limit = int(arg)
        elif opt in ('-f', '--files'):
            dofiles = True

    if dofiles and len(args) == 0:
        print "ERROR: the -f|--files requires a list of files to process!"
        return True

    if limit < 0:
        print "ERROR: -l|--limit value must be greater than 0!"
        return True

    ncpu = CONFIG.get('ncpu', 1) # get a good default number
    try:
        ncpu = cpu_count()
    except NotImplementedError:
        pass

    if nproc > ncpu:
        print "WARNING: nproc: ({}) > ncpu ({})!".format(nproc, ncpu)

    if nproc == 0:
        nproc = ncpu

    if verbose:
        print '----------------------------------'
        print 'NAIP year: {}'.format(year)
        print 'Num Procs: {}'.format(nproc)
        if limit > 0:
            print 'Limit: {}'.format(limit)
        if dofiles:
            print 'Processing list of files.'
        else:
            print 'Processing files from database.'
        print '----------------------------------'

    processes = []

    # we process a list of files here
    if dofiles:
        if len(args) < nproc:
            nproc = len(args)

        n = int(len(args)/nproc + 0.5)

        for m in range(nproc):
            p = Process( target=processNaipFromList,
                         args=(args[m*n:(m+1)*n], m, year) )
            p.start()
            processes.append(p)

    # we process files from a DB query here
    else:

        for m in range(nproc):
            p = Process( target=processNaipFromQuery,
                         args=(nproc, m, limit, year) )
            p.start()
            processes.append(p)

    # wait for the processes to all finish
    for p in processes:
        p.join()


