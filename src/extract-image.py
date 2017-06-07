#!/usr/bin/env python

import os
import sys
import getopt
import psycopg2
import subprocess
import gdal

# globals
TMPDIR = "/tmp"
DOQQS = "/u/ror/buildings/data/naip/doqqs/2014/"
DBUSER="postgres"
DBNAME="buildings"
DBPORT="5435"
DBHOST="localhost"
SHP_TABLE = "naipbbox2014"
DEG_PER_PIXEL = 0.000005836467370

IMAGE_EXT = {'GTiff':'tif', 'JPEG':'jpg', 'PNG':'png', 'BMP':'bmp'}
IMAGE_OPTS = {'GTiff':['-co', 'TILED=YES', '-co', 'COMPRESS=JPEG', '-co', 'JPEG_QUALITY=90', '--config', 'GDAL_TIFF_INTERNAL_MASK', 'YES'], 'JPEG':['-co', 'COMPRESS=JPEG', '-co', 'JPEG_QUALITY=90'], 'PNG':[], 'BMP':[]}

DEVNULL = open(os.devnull, 'w')

def Usage():
  print """Usage: extract-image [-w W -h H] [-f format] -o outfile lat lon
             where:
               -w W | --width=W  : width of extracted image, default=256
               -h H | --height=H : height of extracted image, default=256
               -z Z | --zfactor=Z : multiplier to resolution, default=1
               -f format | --format=format : GTiff|JPEG|PNG|BMP, default=GTiff
               -o outfile | --outfile=outfile : filename without .ext
               -t | --test : only report which doqqs will be used
               lat lon : center location for image to be extracted
             notes:
                 outfile.EXT - R,G,B,Alpha,IR image
        """
  sys.exit(2)



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

    #print vrt

    # create an in memory VRT file from the XML
    vrt_ds = gdal.Open( vrt )
    # and copy it to a file
    driver = gdal.GetDriverByName('VRT')
    dst_ds = driver.CreateCopy( vrtfile, vrt_ds )

    dst_ds = None


def getFile( latlon, size, zfact, test, verbose ):
  #print "latlon:", latlon
  #print "size:", size
  #print "zfact:", zfact

  """
     We need the area of +-size/2 pixels about latlon
     At zfact=1 we need 1*DEG_PER_PIXEL
        zfact=2 we need 2*DEG_PER_PIXEL
        etc
     expand gives us the size of the bbox around latlon
     the +100 just allow for some slop
  """
  expand = (size/2.0 + 100) * DEG_PER_PIXEL * zfact

  sql = "select filename from %s where st_intersects(geom, st_expand( st_setsrid( st_makepoint( %f, %f ), 4326 ), %f ))" % (SHP_TABLE, float(latlon[1]), float(latlon[0]), expand)
  #print "sql:", sql

  try:
    conn = psycopg2.connect("dbname='{}' port='{}' host='{}' user='{}'".format(DBNAME, DBPORT,DBHOST,DBUSER))
  except:
    print "Error: Failed to connect to database '{}'".format(DBNAME)
    sys.exit(2)
  conn.set_session(autocommit=True)
  cur = conn.cursor()
  cur.execute(sql)
  rows = cur.fetchall()
  conn.close()

  if len(rows) == 0:
    return []

  files = []

  if test or verbose:
    for row in rows:
      print row[0]
    if test:
      sys.exit(0)

  for row in rows:
    filename = row[0]
    name = filename[:26] + '.tif'
    subdir = filename[2:7]
    f = os.path.join( DOQQS, subdir, name )
    files.append(f)

  return files

def extractImage(files, ofile, oformat, height, width, zfact, latlon, verbose):

  cx = float(latlon[1])
  cy = float(latlon[0])
  dx = width / 2.0 * DEG_PER_PIXEL * zfact
  dy = height / 2.0 * DEG_PER_PIXEL * zfact
  ulx = cx - dx
  uly = cy + dy
  lrx = cx + dx
  lry = cy - dy

  ofile = ofile + IMAGE_EXT[oformat]
  vfile = ofile + '.vrt'

  bands = []

  for f in files:
    bands.append( [f, 1, 'Red']   )
    bands.append( [f, 2, 'Green'] )
    bands.append( [f, 3, 'Blue']  )
    bands.append( [f, 5, 'Alpha'] )  # Alpha band
    bands.append( [f, 4, 'Gray']  )  # IR band

  createVRT( vfile, bands )

  # create the final vrt file with appropriate mask band defined
  cmd = ['gdal_translate', '-b', '1', '-b', '2', '-b', '3', '-b', '5',
         '-mask', '4', '-of', oformat, 
         '-projwin',  str(ulx), str(uly), str(lrx), str(lry)] + \
         IMAGE_OPTS[oformat] + [vfile, ofile]
  if verbose: print ' '.join(cmd)
  subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

  if os.path.exists( ofile + '.aux.xml' ):
    os.remove( ofile + '.aux.xml' )
  if os.path.exists( vfile ):
    os.remove( vfile )

  return ofile



def Main(argv):

  height = 256
  width = 256
  oformat = 'GTiff'
  outfile = ''
  zfactor = 1
  test = False
  verbose = False

  try:
    opts, args = getopt.getopt( argv, "w:h:z:f:o:tv", ["width", "height", "zfactor", "format", "outfile", "test", "verbose", "help"] )
  except getopt.GetoptError:
    Usage()

  #print "opts:", opts
  #print "args:", args

  # process the arguments
  for opt, arg in opts:
    if opt in ('-h', '--height'):
      if int(arg) > 0:
        height = int(arg)
      else:
        Usage()
    elif opt in ('-w', '--width'):
      if int(arg) > 0:
        width = int(arg)
      else:
        Usage()
    elif opt in ('-z', '--zfactor'):
      # changed from int to float --dbb
      if float(arg) > 0.0:
        zfactor = float(arg)
      else:
        Usage()
    elif opt in ('-f', '--format'):
      if not arg in ('GTiff', 'JPEG', 'PNG', 'BMP'):
        Usage()
      oformat = arg
    elif opt in ('-o', '--outfile'):
      outfile = arg
    elif opt in ('-t', '--test'):
      test = True
    elif opt in ('-v', '--verbose'):
      verbose = True
    elif opt == '--help':
      Usage();
    else:
      print "ERROR: unknown options:", opt, arg
      Usage()

  if len(args) != 2:
    Usage()
  if len(outfile) == 0:
    Usage()

  files = getFile( args, max(height, width), zfactor, test, verbose )
  if len(files) == 0:
    print "ERROR: No DOQQs at location", args
    sys.exit(2)

  # extract file
  f = extractImage(files, outfile + '.', oformat, height, width, zfactor, args, verbose)

  print f


if __name__ == "__main__":
  Main( sys.argv[1:] )

