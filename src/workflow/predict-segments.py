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
import psycopg2.extras
from sklearn.externals import joblib
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import GradientBoostingClassifier
from buildings import getInfo


'''
  load a stored trained object,
  read segment data from the database,
  have the ML predict each seg_polys classification
  and save it back to the database
'''


def Usage():
  print '''
Usage: predict-segments <options> trained-object.pkl.gz
    -i|--info  - report available jobid, project, t, s, c parameters
    -b|--table tablename - table to create with class code and probability
    -j|--jobid name    -+
    -p|--project name   |
    -m|--mode ir|tc|fc  |
    -t|--threshold n.n  |- filter dataset to be extracted
    -s|--shape n.n      |
    -c|--compact n.n   -+
    -x|--test - do the prediction but don't write to the database
'''
  sys.exit(2)



def dropAndCreatePredictTable( cur, table ):

  sql = "create schema if not exists predict"
  cur.execute( sql )

  sql = "drop table if exists predict.%s cascade" % ( table )
  cur.execute( sql )

  sql = '''create table predict.%s (
    gid integer not null primary key,
    class integer,
    prob_c0 float8,
    prob_c1 float8,
    prob_c2 float8
    )''' % ( table )
  cur.execute( sql )




def Main(argv):

  table = ''
  jobid = ''
  project = ''
  mode = ''
  threshold = ''
  shape = ''
  compact = ''
  verbose = False
  test = False
  do_info = False

  try:
    opts, args = getopt.getopt(argv, 'hib:j:p:m:t:s:c:vx', ['help', 'table', 'jobid', 'project', 'mode', 'threshold', 'shape', 'compact', 'relevance', 'verbose', 'test'])
  except:
    Usage()

  for opt, arg in opts:
    if opt == '--help':
      Usage()
    elif opt in ('-v', '--verbose'):
      verbose = True
    elif opt in ('-i', '--info'):
      do_info = True
    elif opt in ('-b', '--table'):
      table = re.sub(r'[^a-zA-Z0-9_]', '', arg)
    elif opt in ('-j', '--jobid'):
      jobid = arg
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      mode = arg
    elif opt in ('-t', '--threshold'):
      threshold = arg
    elif opt in ('-s', '--shape'):
      shape = arg
    elif opt in ('-c', '--compact'):
      compact = arg
    elif opt in ('-x', '--test'):
      test = True

  if do_info:
    getInfo(mode, jobid, project)

  if not test and len(table) == 0:
    print "ERROR: -b|--table is a required parameter."
    sys.exit(1)

  if len(args) != 1:
    print "ERROR: extra args or missing trained-object.pkl.gz param!"
    sys.exit(1)

  # load the trained classifier object
  classifier = joblib.load( args[0] )

  try:
    conn = psycopg2.connect("dbname=ma_buildings")
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(1)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  # drop and create predicr.<table>
  if not test:
    dropAndCreatePredictTable( cur, table )

  segtable = 'seg_polys'
  if mode != '':
    segtable = segtable + '_' + mode

  # fetch data for X, y arrays (y is gid values)
  sql = '''select
   area,
   b0_max,
   b0_mean,
   b0_min,
   b0_std,
   b1_max,
   b1_mean,
   b1_min,
   b1_std,
   b2_max,
   b2_mean,
   b2_min,
   b2_std,
   b3_max,
   b3_mean,
   b3_min,
   b3_std,'''

  if mode in ('4b','5b'):
    sql = sql + '''
   b4_max,
   b4_mean,
   b4_min,
   b4_std,'''

  if mode == '5b':
    sql = sql + '''
   b5_max,
   b5_mean,
   b5_min,
   b5_std,'''

  sql = sql + ''' 
   bperim,
   compact,
   frac,
   para,
   perimeter,
   shape,
   smooth,
   dist2road,
   gid
from sd_data.%s a ''' % ( segtable )

  where = []
  if jobid != '':     where.append(" jobid='%s' "   % ( jobid ))
  if project != '':   where.append(" project='%s' " % ( project ))
  if mode != '':      where.append(" mode='%s' "    % ( mode ))
  if threshold != '': where.append(" t=%f "         % ( float(threshold) ))
  if shape != '':     where.append(" s=%f "         % ( float(shape) ))
  if compact != '':   where.append(" c=%f "         % ( float(compact) ))
  if len(where) > 0:
    sql = sql + ' where ' + ' and '.join(where)

  cur.execute( sql )

  X = []
  y = []
  for row in cur:
    X.append(row[:-1])
    y.append(row[-1])

  pclass = classifier.predict( X )
  pproba = classifier.predict_proba( X ).tolist()

  if not test:
    if float(psycopg2.__version__.split(' ')[0]) >= 2.7:
      data = []
      for i in range( len(X) ):
        data.append( [y[i], pclass[i]] + pproba[i] )

      psycopg2.extras.execute_values(cur,
        'insert into predict.' + table + ' values %s',
        data
        )
    else:
      for i in range( len(X) ):
        cur.execute(
          '''insert into predict.%s values (%d, %d, %f, %f, %f)''' %
            tuple( [ table, y[i], pclass[i] ] + pproba[i] )
        )

  conn.close()

  print "%d segmented polygons classified into 'predict.%s' table." % ( len(X), table )
  print "  Count of class 2: ", pclass.tolist().count(2)
  print "  Count of class 1: ", pclass.tolist().count(1)
  print "  Count of class 0: ", pclass.tolist().count(0)




if len(sys.argv) == 1:
  Usage()

if __name__ == '__main__':
  Main(sys.argv[1:])


