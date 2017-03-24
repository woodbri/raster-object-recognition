#!/usr/bin/env python

import os
import sys
import getopt
import psycopg2
import subprocess
import gdal
import re

PIXEL_RESOLUTION = 0.000005836467370

TMPDIR = "/sand480/tmp"
DOQQS = "/wd4m/ca_naip_2016_quads"
TC = "final"
IR = "final-ir"
SHP_TABLE = "naip_3_16_1_1_ca"
OFORMAT = 'GTiff'

IMAGE_EXT = {'GTiff':'tif', 'JPEG':'jpg', 'PNG':'png', 'BMP':'bmp'}
IMAGE_OPTS = {'GTiff':['-co', 'TILED=YES', '-co', 'COMPRESS=JPEG', '-co', 'JPEG_QUALITY=90', '--config', 'GDAL_TIFF_INTERNAL_MASK', 'YES'], 'JPEG':['-co', 'COMPRESS=JPEG', '-co', 'JPEG_QUALITY=90'], 'PNG':[], 'BMP':[]}


DEVNULL = open(os.devnull, 'w')


def Usage():
  print '''
Usage: tile-area.py options
  options:
    --odir|-o path/to/output/dir   -- path to output directory, default: work-tiles
    --bbox|-b xmin,ymin,xmax,ymax  -- bbox for area
    --fips|-f ss[ccc[xxxxx]]       -- fips code for area
    --size|-s tilesize             -- size in pixels of tiles, default: 2000
    --mode|-m tc|fc|ir|4b|5b|all   -- select which files to generate and segment
    --norun|-n                     -- only report statistics and exit
    --onetile                      -- generate one tile and stop for testing
    --help|-h                      -- report help
  notes:
    bbox or fips is required and are mutually exclusive
    4b = R,G,B,mask,IR image
    5b = R,G,B,mask,IR,sobel image
    The sobel band is a sobel filter applied to a (RGB) gray scale image
    it outlines the edges of features.
'''
  sys.exit(2)


'''
   parseBBOX(bbox)

   Extract valuses from 'BOX(-118.21907 33.78389,-118.21883 33.78405)'
   and return [dx, dy]
'''

def parseBBOX(bbox):
  bbox = bbox.strip("BOX() ")
  tmp = bbox.split(',')
  (xmin, ymin) = tmp[0].split()
  (xmax, ymax) = tmp[1].split()
  return [float(xmin), float(ymin), float(xmax), float(ymax)]



def getBboxFromFIPS(fips):
  if fips[0:2] != '06':
    print "ERROR: fips code must be ss[ccc[bbbbb]], where ss=06 (California)!"
    sys.exit(2)

  if len(fips) == 2:
    sql = "select Box2D(st_extent(geom)) from tl_2016_us_county where statefp='%s'" % (fips)
  elif len(fips) == 5:
    sql = "select Box2D(st_extent(geom)) from tl_2016_us_county where geoid='%s'" % ( fips )
  elif len(fips) == 10:
    sql = "select Box2D(st_extent(geom)) from tl_2016_06_cousub where geoid='%s'" % ( fips )
  else:
    print "ERROR: fips code must be ss[ccc[bbbbb]], where ss=06 (California)!"
    sys.exit(2)

  try:
    conn = psycopg2.connect("dbname=auth_buildings")
  except psycopg2.Error as e:
    print "ERROR: Failed to connect to database"
    print e.pgerror
    print e.disg.message_detail
    sys.exit(2)

  conn.set_session(autocommit=True)
  cur = conn.cursor()
  cur.execute( sql )
  row = cur.fetchone()
  conn.close()

  return parseBBOX(row[0])
  


def extractImage(files, ofile, oformat, bbox, size):

  ulx = bbox[0]
  uly = bbox[3]
  lrx = bbox[2]
  lry = bbox[1]

  ofile = ofile + IMAGE_EXT[oformat]

  cmd = ['gdalwarp', '-dstalpha', '-te',  str(ulx), str(lry), str(lrx), str(uly)] + IMAGE_OPTS[oformat] + files + [ofile]
  print "cmd:", ' '.join(cmd)

  #subprocess.call(cmd)
  subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

  return ofile



def getFile( cur, bbox, size ):
  polygon = 'POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))' % (bbox[0], bbox[1], bbox[0], bbox[3], bbox[2], bbox[3], bbox[2], bbox[1], bbox[0], bbox[1])
  sql = "select filename from %s where geom && st_setsrid('%s'::geometry, 4326)" % ( SHP_TABLE, polygon )
  cur.execute( sql )
  rows = cur.fetchall()

  if len(rows) == 0: return []

  files_tc = []
  files_ir = []

  for row in rows:
    filename = row[0]
    name = filename[:26] + '.tif'
    subdir = filename[2:7]
    f_tc = os.path.join( DOQQS, TC, subdir, name )
    files_tc.append(f_tc)
    f_ir = os.path.join( DOQQS, IR, subdir, name )
    files_ir.append(f_ir)

  return [files_tc, files_ir]



def createSobel( tc_f, gt, srs ):
  from skimage import io
  try:
    from skimage import filters
  except:
    from skimage import filter as filters
  from skimage.color import rgb2gray

  # change tile-tc.tif to tile-sb.tif
  sb_f = re.sub(r'-tc', '-sb', tc_f)

  rgb = io.imread( tc_f )
  grey = rgb2gray(rgb)
  im_sobel = filters.sobel( grey )
  io.imsave( sb_f, im_sobel )

  # add georeferencing to image
  sb_ds = gdal.Open( sb_f, gdal.GA_Update )
  sb_ds.SetGeoTransform( gt )
  sb_ds.SetProjection( srs )
  sb_ds = None

  return sb_f


def createVRT(mode, ir_f, tc_f, vrt_f):
  if not mode in ('fc', '4b', '5b'):
    print "ERROR: createVRT called with invalid mode='%s'" % ( mode )
    sys.exit(1)

  ir_ds = gdal.Open( ir_f )
  tc_ds = gdal.Open( tc_f )
  sb_ds = None
  sb_f = None

  xsize = ir_ds.RasterXSize
  ysize = ir_ds.RasterYSize
  gt = ir_ds.GetGeoTransform()
  srs = ir_ds.GetProjectionRef()

  vrt = '''<VRTDataset rasterXSize="%d" rasterYSize="%d">
   <SRS>%s</SRS>
   <GeoTransform>%f, %f, %f, %f, %f, %f</GeoTransform>''' % \
    (xsize, ysize, gdal.EscapeString(srs, scheme = gdal.CPLES_XML), \
     gt[0], gt[1], gt[2], gt[3], gt[4], gt[5])

  if mode == '5b':
    # create the sobel image
    sb_f = createSobel( tc_f, gt, srs )
    sb_ds = gdal.Open( sb_f )

  dstBand = 1
  if mode == 'fc':
    # add the ir band
    dataType = ir_ds.GetRasterBand(1).DataType
    dataTypeName = gdal.GetDataTypeName(dataType)

    # add the Red band from the IR file
    vrt = vrt + '''
      <VRTRasterBand dataType="%s" band="%d">
          <ColorInterp>%s</ColorInterp>
          <SimpleSource>
          <SourceFilename relativeToVRT="1">%s</SourceFilename>
          <SourceBand>%d</SourceBand>
          <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          </SimpleSource>
      </VRTRasterBand>''' % \
      (dataTypeName, dstBand, 'Red', ir_f, 1, \
       xsize, ysize, xsize, ysize)
  else:
    # add the red band
    dataType = tc_ds.GetRasterBand(1).DataType
    dataTypeName = gdal.GetDataTypeName(dataType)

    # add the Red band from the IR file
    vrt = vrt + '''
      <VRTRasterBand dataType="%s" band="%d">
          <ColorInterp>%s</ColorInterp>
          <SimpleSource>
          <SourceFilename relativeToVRT="1">%s</SourceFilename>
          <SourceBand>%d</SourceBand>
          <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          </SimpleSource>
      </VRTRasterBand>''' % \
      (dataTypeName, dstBand, 'Red', tc_f, 1, \
       xsize, ysize, xsize, ysize)

  dstBand = dstBand + 1

  dataType = tc_ds.GetRasterBand(1).DataType
  dataTypeName = gdal.GetDataTypeName(dataType)

  # add the Green Band from the TC file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Green', tc_f, 2, \
     xsize, ysize, xsize, ysize)

  dstBand = dstBand + 1

  # add the Blue band from the TC file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Blue', tc_f, 3, \
     xsize, ysize, xsize, ysize)

  # add the alpha band
  dstBand = dstBand + 1

  # add the Blue band from the TC file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Alpha', tc_f, 4, \
     xsize, ysize, xsize, ysize)


  if mode in ('4b', '5b'):
    # add ir band
    dstBand = dstBand + 1

    dataType = ir_ds.GetRasterBand(1).DataType
    dataTypeName = gdal.GetDataTypeName(dataType)

    # add the IR band from the IR file
    vrt = vrt + '''
      <VRTRasterBand dataType="%s" band="%d">
          <SimpleSource>
          <SourceFilename relativeToVRT="1">%s</SourceFilename>
          <SourceBand>%d</SourceBand>
          <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          </SimpleSource>
      </VRTRasterBand>''' % \
      (dataTypeName, dstBand, ir_f, 1, \
       xsize, ysize, xsize, ysize)

  if mode == '5b':
    # add the sobel band
    dstBand = dstBand + 1

    dataType = sb_ds.GetRasterBand(1).DataType
    dataTypeName = gdal.GetDataTypeName(dataType)

    # add the Sobel band from the sobel file
    vrt = vrt + '''
      <VRTRasterBand dataType="%s" band="%d">
          <SimpleSource>
          <SourceFilename relativeToVRT="1">%s</SourceFilename>
          <SourceBand>%d</SourceBand>
          <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
          </SimpleSource>
      </VRTRasterBand>''' % \
      (dataTypeName, dstBand, sb_f, 1, \
       xsize, ysize, xsize, ysize)

  # close up the XML
  vrt = vrt + '''
</VRTDataset>'''

  # create an in memory VRT file from the XML
  vrt_ds = gdal.Open( vrt )
  # and copy it to a file
  driver = gdal.GetDriverByName('VRT')
  dst_ds = driver.CreateCopy( vrt_f, vrt_ds )

  dst_ds = None
  tc_ds = None
  ir_ds = None
  vrt_ds = None
  sb_ds = None


def createFalseColorVRT(ir_f, tc_f, vrt_f):
  ir_ds = gdal.Open( ir_f )
  tc_ds = gdal.Open( tc_f )

  xsize = ir_ds.RasterXSize
  ysize = ir_ds.RasterYSize
  gt = ir_ds.GetGeoTransform()
  srs = ir_ds.GetProjectionRef()

  vrt = '''<VRTDataset rasterXSize="%d" rasterYSize="%d">
   <SRS>%s</SRS>
   <GeoTransform>%f, %f, %f, %f, %f, %f</GeoTransform>''' % \
    (xsize, ysize, gdal.EscapeString(srs, scheme = gdal.CPLES_XML), \
     gt[0], gt[1], gt[2], gt[3], gt[4], gt[5])

  dataType = ir_ds.GetRasterBand(1).DataType
  dataTypeName = gdal.GetDataTypeName(dataType)
  dstBand = 1

  # add the Red band from the IR file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Red', ir_f, 1, \
     xsize, ysize, xsize, ysize)

  dstBand = dstBand + 1

  dataType = tc_ds.GetRasterBand(1).DataType
  dataTypeName = gdal.GetDataTypeName(dataType)

  # add the Green Band from the TC file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Green', tc_f, 2, \
     xsize, ysize, xsize, ysize)

  dstBand = dstBand + 1

  # add the Blue band from the TC file
  vrt = vrt + '''
    <VRTRasterBand dataType="%s" band="%d">
        <ColorInterp>%s</ColorInterp>
        <SimpleSource>
        <SourceFilename relativeToVRT="1">%s</SourceFilename>
        <SourceBand>%d</SourceBand>
        <SrcRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        <DstRect xOff="0" yOff="0" xSize="%d" ySize="%d"/>
        </SimpleSource>
    </VRTRasterBand>''' % \
    (dataTypeName, dstBand, 'Blue', tc_f, 3, \
     xsize, ysize, xsize, ysize)

  # close up the XML
  vrt = vrt + '''
</VRTDataset>'''

  # create an in memory VRT file from the XML
  vrt_ds = gdal.Open( vrt )
  # and copy it to a file
  driver = gdal.GetDriverByName('VRT')
  dst_ds = driver.CreateCopy( vrt_f, vrt_ds )

  dst_ds = None
  tc_ds = None
  ir_ds = None
  vrt_ds = None



def Main(argv):
  norun = False
  size = 2000
  bbox = []
  mode = '5b'
  odir = 'work-tiles'
  onetile = False

  try:
    opts, args = getopt.getopt(argv, 'o:b:f:s:m:nh', ['odir', 'bbox', 'fips', 'size', 'norun', 'help', 'onetile', 'mode'])
  except getopt.GetoptError as err:
    print str(err)
    Usage()

  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    elif opt in ('-n', '--norun'):
      norun = True
    elif opt == '--onetile':
      onetile = True
    elif opt in ('-o', '--odir'):
      odir = arg
    elif opt in ('-m', '--mode'):
      if arg in ('tc','fc','ir','4b', '5b', 'all'):
        mode = arg
      else:
        print "ERROR: mode = tc|fc|ir|4b|5b|all (not: %s)!" % (arg)
        sys.exit(2)
    elif opt in ('-s', '--size'):
      size = int(arg)
      if not size>0:
        print "ERROR: size must be > 0"
        sys.exit(2)
    elif opt in ('-b', '--bbox'):
      tmp = arg.split(',')
      if len(bbox) != 0 or len(tmp) != 4:
        print tmp
        Usage()
      tmp = list(map(float, tmp))
      for x in tmp:
        if abs(x) > 180.:
          print "ERROR: bbox values must be -180 <= value <= 180"
          sys.exit(2)
      if tmp[0]>tmp[2] or tmp[1]>tmp[3]:
        print "ERROR: bbox min values must be less then max values"
        sys.exit(2)
      bbox = tmp
    elif opt in ('-f','--fips'):
      if len(bbox) != 0: Usage()
      bbox = getBboxFromFIPS(arg)

  if len(bbox) == 0:
    print "ERROR: No BBOX found to process!"
    Usage()

  # bbox width and height in degrees
  dx = bbox[2]-bbox[0]
  dy = bbox[3]-bbox[1]

  # bbox width and height in pixels
  width = dx / PIXEL_RESOLUTION
  height = dy / PIXEL_RESOLUTION

  # number of tiles in x and y
  ntilex = int(width/size + 0.5)
  ntiley = int(height/size + 0.5)

  # tile width/height in degees
  tsize = size * PIXEL_RESOLUTION

  print "dx:", dx
  print "dy:", dy
  print "width:", width
  print "height:", height
  print "ntilex:", ntilex
  print "ntiley:", ntiley
  print "size:", size
  print "tsize:", tsize

  if norun: exit(0)

  try:
    conn = psycopg2.connect("dbname=auth_buildings")
  except psycopg2.Error as e:
    print "ERROR: Failed to connect to database"
    print e.pgerror
    print e.diag.message_detail
    sys.exit(2)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  for col in range(ntilex):
    xmin = bbox[0] + col * tsize
    xmax = bbox[0] + (col+1) * tsize
    for row in range(ntiley):
      print "Processing col: %d, row: %d ... " % (col, row)

      ymin = bbox[1] + row * tsize
      ymax = bbox[1] + (row+1) * tsize

      tbox = [xmin, ymin, xmax, ymax]

      # create a file for the input
      doqqs = getFile( cur, tbox, size )
      #print '    ', doqqs

      print "bbox:", bbox
      print "tbox:", tbox
      print "n doqqs:", len(doqqs[0])

      basename = 'tile-%d-%d' % (col, row)

      if not os.path.exists( os.path.join(odir, basename) ):
        os.makedirs( os.path.join(odir, basename) )

      files = []

      if mode in ('tc', 'fc', '4b', '5b', 'all'):
        # extract TC file
        ofile = os.path.join(odir, basename, 'tile-tc.')
        f_tc = extractImage(doqqs[0], ofile, OFORMAT, tbox, size)
        print '    f_tc:', f_tc
        files.append( f_tc )

      if mode in ('ir', 'fc', '4b', '5b', 'all'):
        # extract IR file
        ofile = os.path.join(odir, basename, 'tile-ir.')
        f_ir = extractImage(doqqs[1], ofile, OFORMAT, tbox, size)
        print '    f_ir:', f_ir
        files.append( f_ir )

      if mode in ('ir', 'all'):
        # create a RGB grayscale vrt file from the single band IR
        ifile = os.path.join(odir, basename, 'tile-ir.'+IMAGE_EXT[OFORMAT])
        ofile = os.path.join(odir, basename, 'tile-ir.vrt')
        cmd = ['gdalbuildvrt', '-separate', '-b', '1',  ofile, f_ir, f_ir, f_ir]
        subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)
        print '    f_ir:', ofile
        files.append( ofile )

      if mode in ('fc', 'all'):
        # create a RGB false color from IR and B,G from tc files
        f_fc = os.path.join(odir, basename,'tile-fc.vrt')
        #createFalseColorVRT( f_ir, f_tc, f_fc )
        createVRT( 'fc', f_ir, f_tc, f_fc )
        print '    f_fc:', f_fc
        files.append( f_fc )

      if mode in ('4b', 'all'):
        # create a R, G, B, IR file from tc and ir files
        f_4b = os.path.join(odir, basename,'tile-4b.vrt')
        createVRT( '4b', f_ir, f_tc, f_4b )
        print '    f_4b:', f_4b
        files.append( f_4b )

      if mode in ('5b', 'all'):
        # create a RGB false color from IR and B,G from tc files
        f_5b = os.path.join(odir, basename,'tile-5b.vrt')
        createVRT( '5b', f_ir, f_tc, f_5b )
        print '    f_5b:', f_5b
        files.append( f_5b )

      # segmentize image
      # load polygons to DB

      if onetile: break
    if onetile: break

if __name__ == '__main__':
  Main(sys.argv[1:])

