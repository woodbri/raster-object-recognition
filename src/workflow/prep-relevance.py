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
import getopt
import psycopg2
from buildings import getInfo

'''
  create a table associated with subset of seg_polys and assign
  to a class based on mutual percent overlap with a truth polygon

  Within our training set of buildings we have a large number of small buildings
  that are classified as commercial.
  56,447 <  90 sq-m,  969 sq-ft the size of a small residential house
  90,420 < 150 sq-m, 1615 sq-ft the size of a large residential house
  --minsize sq-m will allow these to be filtered out.
'''

def Usage():
  print '''
Usage: prep-relevance.py <options>
  options:
    -h|--help
    -i|--info  - report available jobid, project, t, s, c parameters and exit
    -b|--table tablename - table to create with relevance and class code (required)
    -j|--jobid name          -+
    -p|--project name         |
    -m|--mode ir|tc|fc|4b|5b  |- filters for selecting specific records
    -t|--threshold n.n        |
    -s|--shape n.n            |
    -c|--compact n.n         -+
    -z|--minsize num         - min size sq-m of training polygons, default: 90
    -v|--verbose
'''
  sys.exit(2)



def sqlForInsert( clss, rtable, btable, jobid, project, mode, threshold, shape, compact, minsize ):

  # shape and compact are numbers between 0 and 1.0
  # they get scaled *10 when converted to file names
  threshold = float(threshold)
  shape = float(shape)
  compact = float(compact)
  if shape < 1.0: shape = shape * 10
  if compact < 1.0: compact = compact * 10

  table = 'seg_polys'
  if mode != '': table = 'seg_polys_' + mode

  # 18mar17  CONSIDER 
  #   
  #  ( area(targ) - area(intersect(seg_poly,targ) )  +   abs( area(seg_poly) - area(targ) )
  #       st_area(c.geom) - st_area(st_intersection(a.geom,c.geom))
  #         + abs(st_area(a.geom) - st_area(c.geom)),
  #
  #  xxchange to  (area(targ) - area(intersect(seg_poly,targ)))/area(seg_poly)
  #  converging towards 0 as a perfect fit
  #
  # 20mar17 sew
  # coverage1 is a quantity and not a ratio. A better metric for error of fit
  # might be:
  # (area(target)-area(intersect) + area(segment)-area(intersect)) /
  #   (area(target) + area(segment))
  #
  # or refactoring the numerator to:
  #   area(target) + areas(segment) - 2*area(intersect)
  #
  sql = '''insert into relevance."%s"
  select a.gid,
         %d::integer,
         -- pctoverlap
         st_area(st_intersection(a.geom,c.geom))/st_area(a.geom),
         -- coverage1
         (st_area(c.geom) + st_area(a.geom) - 
            2.0*st_area(st_intersection(a.geom,c.geom))) /
            (st_area(c.geom) + st_area(a.geom)),
         -- coverage2
         (st_area(c.geom) - st_area(st_intersection(a.geom,c.geom)))
           / st_area(a.geom),
         -- centr_seg
         st_intersects(st_centroid(a.geom), c.geom),
         -- centr_trg
         st_intersects(st_centroid(c.geom), a.geom)
    from %s a                                       -- (3) segment polygons
         join %s c on st_intersects(a.geom, c.geom) -- (4) building polygons
         left outer join relevance."%s" b on a.gid=b.gid
   where b.class is null ''' % ( rtable, clss, table, btable, rtable )

  where = []
  if jobid != '':     where.append(" jobid='%s' "   % ( jobid ))
  if project != '':   where.append(" project='%s' " % ( project ))
  if mode != '':      where.append(" mode='%s' "    % ( mode ))
  if threshold != '': where.append(" t=%f "         % ( threshold ))
  if shape != '':     where.append(" s=%f "         % ( shape ))
  if compact != '':   where.append(" c=%f "         % ( compact ))
  if minsize != None: where.append(" c.shp_area_m>%f " % ( minsize ))

  if len(where) > 0:
    sql = sql + ' and ' + ' and '.join(where)

  sql = sql + " on conflict do nothing "

  #print sql

  ## 18mar17 CONSIDER add boolean cols  'centr_seg' and 'centr_trg'
  ##  first is true when the centroid of the segmented poly intersects the target
  ##  second is true when the centroid of the target intersects the segmented poly


  return sql



def Main(argv):

  table = ''
  jobid = ''
  project = ''
  mode = ''
  threshold = ''
  shape = ''
  compact = ''
  verbose = False
  info = False
  minsize = 90.0


  try:
    opts, args = getopt.getopt(argv, 'hib:j:p:m:t:s:c:vz:', ['help', 'table', 'jobid', 'project', 'mode', 'threshold', 'shape', 'compact', 'verbose', 'minsize'])
  except:
    Usage()

  for opt, arg in opts:
    if opt == '--help':
      Usage()
    elif opt in ('-i', '--info'):
      info = True
    elif opt in ('-b', '--table'):
      table = re.sub(r'[^a-zA-Z0-9_]', '', arg)
    elif opt in ('-j', '--jobid'):
      jobid = arg
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      if arg in ('ir', 'tc', 'fc', '4b', '5b'):
        mode = arg
    elif opt in ('-t', '--threshold'):
      threshold = arg
    elif opt in ('-s', '--shape'):
      shape = arg
    elif opt in ('-c', '--compact'):
      compact = arg
    elif opt in ('-z', '--minsize'):
      minsize = float(arg)
    elif opt in ('-v', '--verbose'):
      verbose = True

  if info:
    getInfo(mode, jobid, project)

  if len(table) == 0:
    print "ERROR: -b|--table is a required parameter."
    sys.exit(1)

  try:
    conn = psycopg2.connect("dbname=ma_buildings")
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(2)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  sql = 'create schema if not exists relevance'
  if verbose: print sql
  cur.execute( sql )

  sql = 'drop table if exists relevance."%s" cascade' % ( table )
  if verbose: print sql
  cur.execute( sql )

  sql = '''create table if not exists relevance."%s" (
gid integer not null primary key,
class integer,
pctoverlap float8,
coverage1 float8,
coverage2 float8,
centr_seg boolean,
centr_trg boolean
)''' % ( table )
  if verbose: print sql
  cur.execute( sql )
  conn.commit()

  '''
  There is a potential problem with the following:
  If a segment polygon intersects both a commercial building and regular
  building is will get the percentage associated with the commerical building.

  To check if it intersects with both will be time consuming and the logic
  gets more complicated. We will have to remove the filter class is null,
  then try to INSERT it and get a primary key violation, the follow up with
  and UPDATE based on which intersection is a greater percentage.

  I'm ignoring this problem for the time being and may or may not change this.
  '''

  print "Creating relevance percentage for commercial building ... "
  sql = sqlForInsert( 2, table, 'train_bldgs_08mar17', jobid, project, mode, threshold, shape, compact, minsize )
  if verbose: print sql
  cur.execute( sql )

  print "Creating relevance percentage for other buildings ... "

  # sql to use OSM buildings
  #sql = sqlForInsert( 1, table, 'raw.areas', jobid, project, mode, threshold, shape, compact, None )

  # sql to use LA county Auth buildings
  sql = sqlForInsert( 1, table, 'la14.lariac4_buildings_2014', jobid, project, mode, threshold, shape, compact, None )
  if verbose: print sql
  cur.execute( sql )

  print "Done."
  print

  sql = """select class,
                  count(*),
                  min(pctoverlap),
                  avg(pctoverlap),
                  max(pctoverlap),
                  stddev(pctoverlap),
                  min(coverage1),
                  avg(coverage1),
                  max(coverage1),
                  stddev(coverage1),
                  min(coverage2),
                  avg(coverage2),
                  max(coverage2),
                  stddev(coverage2),
                  sum(case when centr_seg then 1 else 0 end),
                  sum(case when centr_trg then 1 else 0 end)
             from relevance."%s" group by class order by class desc""" % ( table )

  if verbose: print sql
  cur.execute(sql)
  for row in cur:
    print "Class: ", row[0]
    print "..Polygons in class: ", row[1]
    print "..Min pct overlap: ", row[2]
    print "..Average pct overlap: ", row[3]
    print "..Max pct overlap: ", row[4]
    print "..StdDev pct overlap: ", row[5]
    print "..Min coverage1: ", row[6]
    print "..Average coverage1: ", row[7]
    print "..Max coverage1: ", row[8]
    print "..StdDev coverage1: ", row[9]
    print "..Min coverage2: ", row[10]
    print "..Average coverage2: ", row[11]
    print "..Max coverage2: ", row[12]
    print "..StdDev coverage2: ", row[13]
    print "..Centr_Seg count: ", row[14]
    print "..Centr_Trg count: ", row[15]
  conn.close()


if len(sys.argv) == 1:
  Usage()

if __name__ == '__main__':
  Main(sys.argv[1:])

