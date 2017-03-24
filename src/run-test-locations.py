


import os
import sys
import getopt
import subprocess
import urlparse
import psycopg2
from segment import segment
from workflow import workflow
from automate import automate
import rank
import outline
import tools


DEVNULL = open(os.devnull, 'w')

MAXZOOM = 19

def Usage():
  print """Usage: run-test-locations.py options [-q sample_count | locations.txt]
    where options are:
      [-d outdir] - output directory to put results into, default: work
      [-r rundir] - this run directory inside outdir, default: .
      [-m mode]   - mode=tc|ir|fc|all, default: all
      [-q N]      - query database for about N samples
      [-w W]   - image width, default: 256
      [-h H]   - image height, default: 256
      [-z Z]   - zoom factor, z<0 use url zoom, default: 1
      [-t T]   - T1[,T2,...] thresholds, default: 30,50
      [-s S]   - S1[,S2,...] shape rate, default: 0.5
      [-c C]   - C1[,C2,...] compact/smoothness, default: 0.3,0.7
  """
  sys.exit(2)

'''
   read_file( fname )

   reads a file with urls to out map and parse out some params
   also looks for "dir: dirname" and sets basedir global
   returns:
   [
     [lat, lon, "basedir/tcase", url, zoom ],
     ...
   ]
'''
def read_file( fname ):
  results = []
  basedir = ''
  with open( fname ) as f:
    cnt = 0
    for line in f:
      cnt = cnt + 1
      line = line.strip()
      if len(line) == 0 or line[0] == '#':
        continue
      elif line[0:4].lower() == 'dir:':
        basedir = line[4:].strip()
      else:
        # this should be a url
        url0 = urlparse.urlparse( line )
        url = urlparse.parse_qs( url0.query )
        results.append([url['lat'][0], url['lon'][0], basedir + str(len(results)+1), line, url['zoom'][0]])
  return results


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
  return (float(xmax)-float(xmin), float(ymax)-float(ymin))
  


'''
   query_sample( sample_count )

   query the database, for sample buildings
   returns:
   [
     [lat, lon, "basedir/tcase", url, zoom, image_w, image_h ],
     ...
   ]

'''
def query_sample( sample_count ):
  try:
    conn = psycopg2.connect("dbname=ma_buildings")
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(2)

  cur = conn.cursor()

  sql = 'select st_y(st_centroid(geom)) as lat, st_x(st_centroid(geom)) as lon, Box2D(geom) from training_buildings '

  if sample_count > 0:
    cur.execute('select count(*) from training_buildings')
    cnt = cur.fetchone()
    size = sample_count * 100.0 / float(cnt[0])

    sql = sql + 'tablesample bernoulli(%f) repeatable(123456)' % size

  print sql
  cur.execute(sql)

  doqq_resolution = 0.000006124881549

  data = []
  for row in cur:
    lat = float(row[0])
    lon = float(row[1])
    (dx, dy) = parseBBOX(row[2])

    # compare dx/res and dy/res to w, h
    building_bbox_w = round(dx/doqq_resolution)
    building_bbox_h = round(dy/doqq_resolution)

    # and compute zoom factor
    zoom = 19

    # construct url
    url = '/osmb/?zoom=%d&lat=%f&lon=%f&layers=00000B0TTFFFFF' % (zoom, lat, lon) 

    # set the path
    path = 'sample-' + str(len(data)+1)
    
    data.append([lat, lon, path, url, zoom, building_bbox_w+50, building_bbox_h+50])

  conn.close()

  return data


    

def Main(argv):

  width     = -256
  height    = -256
  zfactor   = 1
  threshold = [60]
  shape     = [0.9]
  compact   = [0.5] # [0.1, 0.5, 0.7]
  odir      = 'work'
  rdir      = '.'
  mode      = 'all'
  query     = False
  sample_count = 0

  try:
    opts, args = getopt.getopt( argv, "d:r:m:w:h:z:t:s:c:q:", ["help", "outdir", "rundir", "query", "mode", "width", "height", "zfactor", "threshold", "shape", "compact"])
  except getopt.GetoptError:
    Usage()

  for opt, arg in opts:
    if opt == '--help':
      Usage()
    elif opt in ('-d', '--outdir'):
      odir = arg
    elif opt in ('-r', '--rundir'):
      rdir = arg
    elif opt in ('-q', '--query'):
      query = True
      sample_count = int(arg)
    elif opt in ('-m', '--mode'):
      if arg in ('tc','ir','fc','all'):
        mode = arg
      else:
        print "ERROR: invalid argument for mode ("+arg+")\n"
        Usage()
    elif opt in ('-h', '--height'):
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
      zfactor = float(arg)
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
    else:
        print "ERROR: unknown options:", opt, arg
        Usage()


  '''
  data = [[lat,lon,dir,url,zoom],...]
  '''
  if query:
    data = query_sample( sample_count )
  else:
    data = read_file( args[0] )

  for d in data:
    print d

    # default width and height are -256
    # if default, use computed, else use cmd line values
    if query:
      if width<0:
        width = d[5]
      if height<0:
        height = d[6]

    # make dirs if needed
    path = os.path.join( odir, rdir, d[2] )
    if not os.path.exists( path ):
      os.makedirs( path )

    # extract the images

    ofile = os.path.join( odir, rdir, d[2], "test" )

    if zfactor < 0:
      zoom = MAXZOOM - int(d[4]) + 1
    else:
      zoom = zfactor

    # take abs(width or height) to make default values positive
    cmd = ['extract-image.py', '-w', str(int(abs(width))), '-h', str(int(abs(height))), '-z', str(zoom), '-o', ofile, str(d[0]), str(d[1]) ]
    print cmd
    subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)

    # process the images

    print "t:", threshold
    print "s:", shape
    print "c:", compact

    '''
    files = automate( image, t=threshold, s=shape, c=compact,
                      do_stats=False, do_colorize=False, do_train=False,
                      do_classify=False, do_outline=True, do_lineup=True)
    '''

    files = []

    if mode in ('tc', 'all'):
      f  = automate( ofile + "-tc.tif", t=threshold, s=shape, c=compact,
                     do_stats=True, do_colorize=True, do_train=True,
                     do_classify=True, do_outline=True, do_lineup=True)
      files = files + f

    if mode in ('ir', 'all'):
      f = automate( ofile + '-ir.vrt',
                    t=threshold, s=shape, c=compact,
                    do_stats=True, do_colorize=True, do_train=True,
                    do_classify=True, do_outline=True, do_lineup=True)
      files = files + f

    if mode in ('fc', 'all'):
      f = automate( ofile + '-fc.vrt',
                    t=threshold, s=shape, c=compact,
                    do_stats=True, do_colorize=True, do_train=True,
                    do_classify=True, do_outline=True, do_lineup=True)
      files = files + f

    files.append(ofile + "-tc.tif")
    files.append(ofile + "-fc.vrt")
    files.append(ofile + "-ir.vrt")
    for f in files:
      if f[-3:] == 'tif':
        cmd = ['convert', f, f + '.jpg']
        subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)
      elif f[-3:] == 'vrt':
        cmd = ['gdal_translate', '-of', 'JPEG', f, f + '.jpg']
        subprocess.call(cmd, stdout=DEVNULL, stderr=subprocess.STDOUT)


  if rdir == '.':
    hfile = 'lineup.html'
    html = os.path.join( odir, hfile )
  else:
    hfile = 'lineup.html'
    html = os.path.join( odir, rdir, hfile )


  # generate lineup.html
  f = open( html, 'wb' )

  # write file header
  f.write("""<html>
<head>
<title>Lineups</title>
</head>
<body>
""")
  
  # write block for each sample
  for d in data:

    if zfactor < 0:
      zoom = MAXZOOM - int(d[4]) + 1
    else:
      zoom = zfactor

    ofile = os.path.join( d[2], "test" )
    f.write("<div>\n <a href=\""+d[3]+"\" target=\"_maps\">"+d[3]+"</a><br>\n")
    if mode in ('tc','all'):
      img = ofile + "-tc.tif.jpg"
      img_lu = ofile + "-tc.tif_lineup.tif.jpg" 
      f.write(" <table><tr><td><img src=\""+img+"\"><br>\n<ul><li>lat: "+
              str(d[0])+"</li>\n<li>lon: "+str(d[1])+"</li>\n<li>z: "+str(zoom)+
              "</li>\n<li>t: "+str(threshold)+
              "</li>\n<li>s: "+str(shape)+"</li>\n<li>c: "+
              str(compact)+"</ul></td>\n")
      f.write("<td><img src=\""+img_lu+"\"></td><tr>\n </table>\n<br><hr>\n")
    if mode in ('tc','all'):
      img = ofile + "-fc.vrt.jpg"
      img_lu = ofile + "-fc.vrt_lineup.tif.jpg" 
      f.write(" <table><tr><td><img src=\""+img+"\"><br>\n<ul><li>lat: "+
              str(d[0])+"</li>\n<li>lon: "+str(d[1])+"</li>\n<li>z: "+str(zoom)+
              "</li>\n<li>t: "+str(threshold)+
              "</li>\n<li>s: "+str(shape)+"</li>\n<li>c: "+
              str(compact)+"</ul></td>\n")
      f.write("<td><img src=\""+img_lu+"\"></td><tr>\n </table>\n<br><hr>\n")
    if mode in ('tc','all'):
      img = ofile + "-ir.vrt.jpg"
      img_lu = ofile + "-ir.vrt_lineup.tif.jpg" 
      f.write(" <table><tr><td><img src=\""+img+"\"><br>\n<ul><li>lat: "+
              str(d[0])+"</li>\n<li>lon: "+str(d[1])+"</li>\n<li>z: "+str(zoom)+
              "</li>\n<li>t: "+str(threshold)+
              "</li>\n<li>s: "+str(shape)+"</li>\n<li>c: "+
              str(compact)+"</ul></td>\n")
      f.write("<td><img src=\""+img_lu+"\"></td><tr>\n </table>\n<br><hr>\n")
    f.write("</div>\n")

  f.write("</body>\n</html>\n")
  f.close()


if len(sys.argv) == 1:
  Usage()

if __name__ == "__main__":
  Main( sys.argv[1:] )
    
