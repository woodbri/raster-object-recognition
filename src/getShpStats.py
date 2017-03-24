#!/usr/bin/env python

import os
import sys
from osgeo import ogr
import psycopg2

if len(sys.argv) == 1:
  print "Usage: getShpStats.py dir"
  sys.exit(2)

pcount = 0
fcount = 0

# walk directory and count number of shp files and features in them

for root, dirs, files in os.walk( sys.argv[1] ):
  for f in files:
    if not '.shp' in f: continue
    fcount = fcount + 1
    shp = ogr.Open( os.path.join(root, f) )
    pcount = pcount + shp.GetLayer(0).GetFeatureCount()
    shp = None

print "File count:", fcount
print "Poly count:", pcount

try:
  conn = psycopg2.connect( 'dbname=ma_buildings' )
except:
  print "ERROR: failed to connect to database 'ma_buildings'"
  sys.exit(2)

cur = conn.cursor()
sql = 'select count(*) from seg_polys'
cur.execute( sql )
count = cur.fetchone()

print "Total polygons loaded in seq_polys table: ", count[0]

sql = '''select count(*) from (
  select distinct jobid, project, mode, t, s, c from sd_data.seg_polys ) foo'''
cur.execute( sql )
count = cur.fetchone()

print "Total files loaded in seq_polys table: ", count[0]

conn.close()
