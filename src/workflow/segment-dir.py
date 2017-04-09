#!/usr/bin/env python
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
from osgeo import gdal
import subprocess
#import psycopg2
from segment import segment
from workflow import workflow
from automate import automate
import rank
import outline
import tools


DEVNULL = open(os.devnull, 'w')

def Usage():
  print """Usage: segment-dir options dir
    where options are:
      [-m|--mode ir|fc|tc|4b|5b] - select which file to segmentize
      [-t|--threshold T]   - T1[,T2,...] thresholds, default: 60
      [-s|--shape S]       - S1[,S2,...] shape rate, default: 0.9
      [-c|--compact C]     - C1[,C2,...] compact/smoothness, default: 0.5
      [-v]                 - be verbose
      [--nostats]          - don't generate stats.csv file
      [--nolineup]         - don't generate the lineup image
  """
  sys.exit(2)



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




def segmentize( ofile, mode, threshold, shape, compact, stats, lineup ):

    '''
    files = automate( image, t=threshold, s=shape, c=compact,
                      do_stats=False, do_colorize=False, do_train=False,
                      do_classify=False, do_outline=True, do_lineup=True)
    '''

    files = []

    f = automate( ofile,
                  t=threshold, s=shape, c=compact,
                  do_stats=stats, do_colorize=True, do_train=False,
                  do_classify=False, do_outline=True, do_lineup=lineup)
    files = files + f

    return files


def generateHTML( sfiles, ofiles, odir ):
  html = os.path.join( odir, 'lineup.html' )

  # generate lineup.html
  f = open( html, 'wb' )

  # write file header
  f.write("""<html>
<head>
<title>Lineups</title>
</head>
<body>
""")

  for fs in sfiles:
    # filter ofiles on matching fs and ending in tif
    files = [i for i in ofiles if fs in i and i[-3:] == 'tif']
    htmlWriteSection( f, fs, files )

  f.write("</body>\n</html>\n")
  f.close()


def htmlWriteSection( f, fs, files ):
  mode = fs[-6:-4]

  # get gdalinfo on image
  ds = gdal.Open( fs )
  if ds == None:
    print "WARNING: gdal could not get GetGeoTransform from '%s'!" % (fs)
    return
  info = ds.GetGeoTransform()
  ulx = info[0]
  uly = info[3]
  lrx = ulx + ds.RasterXSize * info[1]
  lry = uly + ds.RasterYSize * info[5]
  clon = (ulx + lrx) / 2.0
  clat = (uly + lry) / 2.0
  width = ds.RasterXSize
  height = ds.RasterYSize
  ds = None

  # limit image size to max 500x500
  iw = width
  ih = height
  ratio = width/height
  if ratio > 1.0:  # width is larger
    if width > 500:
      iw = 500
      ih = int(500.0/ratio)
  else:
    if height > 500:
      ih = 500
      iw = 500 * ratio

  # extract t,s,c from files
  opts = unique(map(lambda x: x[len(fs)+1:len(fs)+9], files))
  opts.pop(-1) # remove lineup 
  t = []
  s = []
  c = []
  for x in opts:
    y = x.split('_')
    if len(y) != 3: continue
    t.append(y[0])
    s.append(y[1])
    c.append(y[2])
  threshold = ','.join(unique(t))
  shape = ','.join(unique(s))
  compact = ','.join(unique(c))

  url = '/osmb/?zoom=19&lat=%f&lon=%f&layers=00000B0TTFFFTFF' % ( clat, clon )
  f.write("<div>\n <a href=\""+url+"\" target=\"_maps\">"+url+"</a><br>\n")
  img = '../' + fs + ".jpg"
  img_lu = '../' + fs + "_lineup.tif.jpg"
  f.write(" <table><tr><td><img height=\""+str(ih)+"\" width=\""+str(iw)+
              "\" src=\""+img+"\"><br>\n<ul><li>lat: "+
              str(clat)+"</li>\n<li>lon: "+str(clon)+"</li>\n<li>z: 19"+
              "</li>\n<li>t: "+str(threshold)+
              "</li>\n<li>s: "+str(shape)+"</li>\n<li>c: "+
              str(compact)+"</ul></td>\n")
  f.write("<td><img src=\""+img_lu+"\"></td><tr>\n </table>\n<br><hr>\n")
  f.write("</div>\n")


def Main(argv):

  threshold = [60]
  shape     = [0.9]
  compact   = [0.5] # [0.1, 0.5, 0.7]
  path      = '.'
  verbose   = False
  stats     = True
  lineup    = True
  mode      = ''

  try:
    opts, args = getopt.getopt( argv, "hvm:t:s:c:", ["help", "verbose", "mode", "threshold", "shape", "compact", "nostats", "nolineup"])
  except getopt.GetoptError:
    Usage()

  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    if opt in ('-v', '--verbose'):
      verbose = True
    elif opt == '--nostats':
      stats = False
    elif opt == '--nolineup':
      lineup = False
    elif opt in ('-m', '--mode'):
      if mode in ('ir', 'fc', 'tc', '4b', '5b'):
        mode = arg
    elif opt in ('-t', '--threshold'):
      threshold = []
      for x in arg.split(','):
        if int(x) > 0:
          threshold.append(int(x))
      if len(threshold) == 0:
        print "ERROR: invalid argument for -t|--threshold (t > 0)"
        sys.exit(2)
    elif opt in ('-s', '--shape'):
      shape = []
      for x in arg.split(','):
        if float(x) < 0.0 or float(x) > 1.0:
          pass
        else:
          shape.append(float(x))
      if len(shape) == 0:
        print "ERROR: invalid argument for -s|--shape (0 <= s <= 1.0)"
        sys.exit(2)
    elif opt in ('-c','--compact'):
      compact = []
      for x in arg.split(','):
        if float(x) < 0.0 or float(x) > 1.0:
          pass
        else:
          compact.append(float(x))
      if len(compact) == 0:
        print "ERROR: invalid argument for -c|--compact (0 <= c <= 1.0)"
        sys.exit(2)

  if len(args) != 1:
    Usage()

  ofiles = []
  sfiles = []

  # walk a directory tree and segment all the files
  for root, dirs, files in sorted(os.walk( args[0] )):
    for afile in files:
      if not afile in ('tile-fc.vrt', 'tile-ir.vrt', 'tile-tc.tif', 'tile-4b.vrt', 'tile-5b.vrt'):
        continue

      amode = afile[-6:-4]
      if mode != '' and mode != amode: continue

      ofile = os.path.join(root, afile)
      sfiles.append( ofile )
      print ofile

      if verbose:
        print "segmentize('%s', '%s', %s, %s, %s, %s, %s)" % ( ofile, amode, str(threshold), str(shape), str(compact), str(stats), str(lineup) )

      f = segmentize( ofile, amode, threshold, shape, compact, stats, lineup )
      ofiles = ofiles + f

  for f in ofiles:
    print f

  print
  for f in sfiles:
    print f

  if amode in ('4b', '5b'):
    bands = ['-b', '1', '-b', '2', '-b', '3', '-b', 'mask,4']
  else:
    bands = []

  for f in ofiles + sfiles:
    cmd = ['gdal_translate', '-of', 'JPEG'] + bands + [f, f + '.jpg']
    if verbose:
      print ' '.join(cmd)
      subprocess.call(cmd)
    else:
      subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

  generateHTML( sfiles, ofiles, args[0] )


#---------------------------------------------

if len(sys.argv) == 1:
  Usage()

if __name__ == "__main__":
  Main( sys.argv[1:] )

