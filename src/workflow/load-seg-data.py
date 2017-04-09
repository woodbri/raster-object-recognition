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
import re
import csv
import getopt
import psycopg2
import subprocess
from osgeo import gdal
from osgeo import ogr

gdal.UseExceptions()

'''
For a given input file like project/tcase/test-fc.vrt
the segmentizer generates files in path project/tcase/:

test-fc.vrt_30_05_03.tif
test-fc.vrt_30_05_03.tif_line.tif
test-fc.vrt_30_05_03.tif_rgb.tif
test-fc.vrt_30_05_03.tif_stats.csv
test-fc.vrt_30_05_03.tif.shp

We can generate files given this matrix:

mode |  t  |  S  |  c  |  z  |
------------------------------
 fc  | 30  | 05  | 03  | 19  |
 ir  | 50  | ... | 07  | ... |
 tc  | ... | ... | ... | ... |
------------------------------

We can generate any number of values for t, s, c, and z.

create table sd_data.seg_polys (
  gid serial not null primary key,
  project text,               -- from file path
  tcase text,                 -- from file path
  mode character(2) not null, -- from file name
  t float8 not null,          -- from file name
  s float8 not null,          -- from file name
  c float8 not null,          -- from file name
  img_res float8,             -- resolution of image processed
  id integer,                 -- the following are from the csv file
  area float8,
  b0_max float8,
  b0_mean float8,
  b0_min float8,
  b0_std float8,
  b1_max float8,
  b1_mean float8,
  b1_min float8,
  b1_std float8,
  b2_max float8,
  b2_mean float8,
  b2_min float8,
  b2_std float8,
  b3_max float8,
  b3_mean float8,
  b3_min float8,
  b3_std float8,
  bperim float8,
  compact float8,
  frac float8,
  para float8,
  perimeter float8,
  shape float8,
  smooth float8,              -- last column fron csv
  dist2road float8,           -- computed
  interest integer,           -- updated by web app or by hand
  geom geometry(Polygon, 4326)  -- from the shapefile
);


The following allows be to easily reference any dataset from a mapfile:

create table sd_data.seg_tileindex (
  gid serial not null primary key,
  project text,               -- from file path
  tcase text,                 -- from file path
  mode character(2) not null, -- from file name
  t float8 not null,          -- from file name
  s float8 not null,          -- from file name
  c float8 not null,          -- from file name
  location text,              -- path to test-fc.vrt_30_05_03.tif
  location_line text,         -- path to test-fc.vrt_30_05_03.tif_line.tif
  location_rgb text,          -- path to test-fc.vrt_30_05_03.tif_rgb.tif
  geom geometry (Linestring, 4326)
);

The process to load this data will be a python script that walks the
segmentation output directory structure and loads the files into the
tables described above.


'''

DEVNULL = open(os.devnull, 'w')

SCHEMA = 'sd_data'
TABLE  = 'seg_polys'
TINDEX = 'seg_tileindex'
TBASE = '/s3b/osmb_ab/data/sd_data'

def Usage():
  print """
Usage: load-seg-data.py [options] jobid dir
  where:
    [-c|--create]       - optionally drop and tables
    [-p|--project name] - use this project name instead of dir
    [-n|--nodist2road]  - don't compute dist2road
    [-v|--verbose]      - be verbose
    [-m|--mode ir|fc|fc|4b|5b] 
    jobid - string to uniquely identify this data
    dir   - segmentizer output directory to walk and load
  Note: jobid and project should only contain chars [a-z0-9_]
  """
  sys.exit(2)

'''
  [ox, oy, rx, ry, w, h] = getImageInfo( filename )
  ox - origin x
  oy - origin y
  rx - resolution x
  ry - resolution y
  w  - size x
  h  - size y
'''

def getImageInfo( filename ):
  try:
    ds = gdal.Open( filename )
    gt = ds.GetGeoTransform()
  except RuntimeError, e:
    print 'Unable to getImageInfo(',filename,')'
    print e
    gt = None
    ds = None
    return None

  if ds == None or gt == None:
    gt = None
    ds = None
    return None

  info = [gt[0], gt[3], gt[1], gt[5], ds.RasterXSize, ds.RasterYSize]
  gt = None
  ds = None
  return info



def dropTables(cur, mode):
  sql = "drop table if exists "+SCHEMA+"."+TABLE+"_"+mode+" cascade"
  cur.execute(sql)

  sql = "drop table if exists "+SCHEMA+"."+TINDEX+" cascade"
  cur.execute(sql)



def createTables(cur, mode):
  sql = "create schema if not exists "+SCHEMA
  try:
    cur.execute(sql)
  except:
    pass

  sql = "create table if not exists "+SCHEMA+"."+TABLE+"_"+mode+""" (
  gid serial not null primary key,
  jobid text,                 -- from arguments
  project text,               -- from file path
  tcase text,                 -- from file path
  mode character(2) not null, -- from file name
  t float8 not null,          -- from file name
  s float8 not null,          -- from file name
  c float8 not null,          -- from file name
  img_res float8,             -- resolution of image processed
  id integer,                 -- the following are from the csv file
  area float8,
  b0_max float8,
  b0_mean float8,
  b0_min float8,
  b0_std float8,
  b1_max float8,
  b1_mean float8,
  b1_min float8,
  b1_std float8,
  b2_max float8,
  b2_mean float8,
  b2_min float8,
  b2_std float8,
  b3_max float8,
  b3_mean float8,
  b3_min float8,
  b3_std float8,"""

  if mode in ('4b','5b'):
    sql = sql + """
  b4_max float8,
  b4_mean float8,
  b4_min float8,
  b4_std float8,"""

  if mode == '5b':
    sql = sql + """
  b5_max float8,
  b5_mean float8,
  b5_min float8,
  b5_std float8,"""

  sql = sql +"""
  bperim float8,
  compact float8,
  frac float8,
  para float8,
  perimeter float8,
  shape float8,
  smooth float8,              -- last column fron csv
  dist2road float8,           -- computed
  interest float8,            -- percent under training auth polygon
  geom geometry(Polygon, 4326)  -- from the shapefile
)  """
  cur.execute(sql)

  sql = "create index if not exists "+TABLE+"_geom_idx on "+SCHEMA+"."+TABLE+"_"+mode+" using gist(geom)"
  cur.execute(sql)
  sql = "create index if not exists "+TABLE+"_mode_t_s_c_idx on "+SCHEMA+"."+TABLE+"_"+mode+" using btree(mode,t,s,c)"
  cur.execute(sql)

  sql = "create table if not exists "+SCHEMA+"."+TINDEX+""" (
  gid serial not null primary key,
  jobid text,                 -- from arguments
  project text,               -- from file path
  tcase text,                 -- from file path
  mode character(2) not null, -- from file name
  t float8 not null,          -- from file name
  s float8 not null,          -- from file name
  c float8 not null,          -- from file name
  location text,              -- path to test-fc.vrt_30_05_03.tif
  location_line text,         -- path to test-fc.vrt_30_05_03.tif_line.tif
  location_rgb text,          -- path to test-fc.vrt_30_05_03.tif_rgb.tif
  geom geometry (Polygon, 4326)
)"""
  cur.execute(sql)

  sql = "create index if not exists "+TINDEX+"_geom_idx on "+SCHEMA+"."+TINDEX+" using gist(geom)"
  cur.execute(sql)
  sql = "create index if not exists "+TINDEX+"_mode_t_s_c_idx on "+SCHEMA+"."+TINDEX+" using btree(mode,t,s,c)"
  cur.execute(sql)


def loadFile(cur, mode, jobid, project, r, filename, verbose):
  parts = re.split(r'[-._]', filename)
  #print r, filename, parts

  # work2/garlynn-11
  # test-tc.tif_30_05_07.tif
  # ['test', 'tc', 'tif', '30', '05', '07', 'tif']

  # work-tiles/tile-0-0
  # tile-fc.vrt_60_09_05.tif
  # ['tile', 'fc', 'vrt', '60', '09', '05', 'tif']

  (proj, tcase) = os.path.split( r )
  if project == '':
    project = proj

  # get file resolution and extents [ox, oy, rx, ry, w, h]
  info = getImageInfo( os.path.join(r, filename) )
  if info == None:
    return None

  # open .shp
  try:
    shp = ogr.Open( os.path.join(r, filename+'.shp') )
  except RuntimeError, e:
    print "Failed to open '"+os.path.join(r, filename+'.shp')+"'"
    print e
    return None

  # read _stats.csv
  csvdata = []
  
  try:
    with open( os.path.join(r, filename+'_stats.csv'), 'rb') as fh:
      reader = csv.reader( fh )
      reader.next() # skip the header row
      for row in reader:
        csvdata.append( row )
  except:
    pass

  if len(csvdata) == 0:
    print "Failed to csv '"+os.path.join(r, filename+'_stats.csv')+"'"
    # create a dummy cvsdata array
    for i in range(shp.GetLayer(0).GetFeatureCount()):
      tmp = [0]*21
      tmp[0] = i
      csvdata.append( tmp )

  # sort based on id, it should be sorted
  csvdata.sort(key=lambda x: int(x[0]))

  # join shp and stats and insert into seg_polys table and compute dist2road
  layer = shp.GetLayer(0)
  for i in range(layer.GetFeatureCount()):
    feature = layer.GetFeature(i)
    fid = int(feature.GetField("id"))
    wkt = feature.GetGeometryRef().ExportToWkt()

    # info[ox, oy, rx, ry, w, h]
    data = [jobid, project, tcase, parts[1], parts[3], parts[4], parts[5], str(info[2])]
    cdata = csvdata[fid]
    if len(cdata) == 21:
      cdata = cdata[:14] + ['0','0','0','0'] + cdata[14:]
    elif len(cdata) in (25,29,33):
      pass
    else:
      print "ERROR: '" + os.path.join(r, filename+'_stats.csv') + "' does not have 21, 25, 29 or 33 fields! SKIPPING!"
      sys.exit(1)

    #print "i:", i, ",fid:",fid
    #print "csvdata[fid]:", csvdata[fid]
    #print "data:", data

    #print i, fid, len(data), len(csvdata[fid]), len(cdata), mode

    # add the clause to compute dist2road to insert statement if requested
    if do_dist2road:
      dist2road = """
                   (select st_distance(a.geom, b.geom)
                      from roads b,
                           (select st_makevalid(ST_GeometryFromText('%s', 4326)) as geom) a
                     order by b.geom <-> a.geom limit 1)""" % ( wkt )
    else:
      dist2road = '0.0'

    data = data + cdata + [ wkt, dist2road ]

    sql = 'insert into '+SCHEMA+'.'+TABLE+'_'+mode+ \
      """ (jobid, project, tcase, mode, t, s, c, img_res, id, area,
           b0_max, b0_mean, b0_min, b0_std, 
           b1_max, b1_mean, b1_min, b1_std,
           b2_max, b2_mean, b2_min, b2_std,
           b3_max, b3_mean, b3_min, b3_std,"""
    if mode in ('4b', '5b'):
      sql = sql + """
           b4_max, b4_mean, b4_min, b4_std,"""
    if mode == '5b':
      sql = sql + """
           b5_max, b5_mean, b5_min, b5_std,"""
    sql = sql + """
           bperim, compact, frac, para, perimeter, shape, smooth, geom, dist2road)
           values ('%s','%s','%s','%s',%s,%s,%s,%s,%s,%s,
                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"""
    if mode in ('4b', '5b'):
      sql = sql + "%s,%s,%s,%s,"
    if mode == '5b':
      sql = sql + "%s,%s,%s,%s,"
    sql = sql + """
                   %s,%s,%s,%s,%s,%s,%s,
                   st_makevalid(ST_GeometryFromText('%s', 4326)),
                   %s
                  )"""

    #print sql
    sql = sql % tuple(data)
    if verbose:
      print sql
    cur.execute( sql )

  # info[ox, oy, rx, ry, w, h]
  twkt = 'POLYGON((%f %f,%f %f,%f %f,%f %f,%f %f))' % \
    ( info[0], info[1], \
      info[0]+info[2]*info[4], info[1], \
      info[0]+info[2]*info[4], info[1]+info[3]*info[5], \
      info[0], info[1]+info[3]*info[5], \
      info[0], info[1] )

  data = [jobid, project, tcase, parts[1], parts[3], parts[4], parts[5]]

  # add file to tileindex
  # add file_line.tif to tileindex
  # add file_rgb.tif to tileindex

  if os.path.exists( os.path.join(TBASE, r, filename+'_line.tif') ):
    line = os.path.join(TBASE, r, filename+'_line.tif')
  else:
    line = ''

  if os.path.exists( os.path.join(TBASE, r, filename+'_rgb.tif') ):
    rgb = os.path.join(TBASE, r, filename+'_rgb.tif')
  else:
    rgb = ''

  data = data + [ os.path.join(TBASE, r, filename), line, rgb, twkt ]

  sql = 'insert into '+SCHEMA+'.'+TINDEX+ \
    """ (jobid, project, tcase, mode, t, s, c,
         location, location_line, location_rgb, geom)
        values ('%s','%s','%s','%s',%s,%s,%s,
                nullif('%s',''),nullif('%s',''),nullif('%s',''),
                ST_GeometryFromText('%s', 4326))""" % tuple(data)
  if verbose:
    print sql
  cur.execute( sql )


def loadDir(cur, mode, jobid, project, dirname, verbose):

  for r, dirs, files in os.walk( dirname ):

    # test-fc.vrt_30_05_03.tif
    # test-fc.vrt_30_05_03.tif_line.tif
    # test-fc.vrt_30_05_03.tif_rgb.tif
    # test-fc.vrt_30_05_03.tif_stats.csv
    # test-fc.vrt_30_05_03.tif.shp

    for filename in files:
      if filename[5:7] != mode: continue
      if re.search(r'(?:\d\d\.tif)$', filename, 0):
        loadFile(cur, mode, jobid, project, r, filename, verbose)


def Main(argv):

  try:
    opts, args = getopt.getopt(argv, "cnvhp:m:", ["help", "verbose", "create", "nodist2road", "project", "mode"])
  except getopt.GetoptError:
    Usage()

  do_dist2road = True
  create = False
  verbose = False
  project = ''
  mode = 'tc'

  # process command line args
  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    elif opt in ('-c', '--create'):
      create = True
    elif opt in ('-v', '--verbose'):
      verbose = True
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-n', '--nodist2road'):
      do_dist2road = False
    elif opt in ('-m', '--mode'):
      if arg in ('ir', 'fc', 'tc', '4b', '5b'):
        mode = arg
      else:
        print "Invalid value for mode (%s)!" % ( arg)
        Usage()
      

  if len(args) != 2:
    Usage()

  if not os.path.exists( TBASE ):
    print "ERROR: segment data does not appear to be located in '%s'" % (TBASE)
    sys.exit(2)

  # connect to the database
  try:
    conn = psycopg2.connect("dbname='ma_buildings'")
  except:
    print "Error: Failed to connect to database 'ma_buildings'"
    sys.exit(2)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  jobid = args[0]
  dirname = args[1]

  # drop the tables can recreate them
  if create:
    print "Drop and recreate tables ..."
    dropTables(cur, mode)

  createTables(cur, mode)

  print "Loading files in directory ..."
  loadDir(cur, mode, jobid, project, dirname, verbose)

  print "Done."

  conn.close()


if __name__ == "__main__":
    if len(sys.argv) == 1:
      Usage()

    Main(sys.argv[1:])

