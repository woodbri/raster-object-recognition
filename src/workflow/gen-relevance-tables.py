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
import subprocess


DEVNULL = open(os.devnull, 'w')

def Usage():
  print '''
Usage: gen-relevance-tables.py options
    where options are:
      [-h|--help]          - display help message
      [-j|--jobid name]    - unique name for this job (required)
      [-p|--project name]  - unique project name for this job
      [-m|--mode mm]       - mm = tc|fc|ir|4b|5b|all
      [-t|--threshold T]   - T1[,T2,...] thresholds, required
      [-s|--shape S]       - S1[,S2,...] shape rate, required
      [-c|--compact C]     - C1[,C2,...] compact/smoothness, required
      [-v|--verbose]       - print additional messages
'''
  sys.exit(2)



def printRunSummary( rtables, verbose ):
  try:
    conn = psycopg2.connect("dbname=ma_buildings")
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(2)

  cur = conn.cursor()

  sql = getSqlForEval( rtables )
  if verbose:
    print sql

  cur.execute( sql )

  print
  print "Run Summary:"
  print "run table\t\t\tcount\taverage\tstddev"
  print "---------------------------------------------------------"
  for row in cur:
    out = [row[0], row[1]]
    out.append( coalesce("%.4f", "", row[2]) )
    out.append( coalesce("%.4f", "", row[3]) )
    print "%s\t%d\t%s\t%s" % tuple( out )

  print "---------------------------------------------------------"

  conn.close()



def getSqlForEval( rtables ):
  subs = []
  for t in rtables:
    subs.append(
      "select '%s' as tab, count(*) as count, avg(pctoverlap), stddev(pctoverlap) from \"%s\"" % ( t, t )
    )

  sql = 'select * from (\n' + '\n union all '.join( subs ) + '\n) as foo order by stddev asc'

  return sql



def coalesce(fmt, alt, value):
    if value == None:
      tmp = alt
    else:
      tmp = fmt % (value)
    return tmp



def Main(argv):

  jobid = ''
  project = ''
  mode = ''
  threshold = ''
  shape = ''
  compact = ''
  longpath = False
  verbose = False
  allmodes = ['tc', 'fc', 'ir', '4b', '5b']

  try:
    opts, args = getopt.getopt(argv, 'hj:p:m:t:s:c:v', ['help', 'jobid', 'project', 'mode', 'threshold', 'shape', 'compact', 'verbose'])
  except:
    Usage()

  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    elif opt in ('-j', '--jobid'):
      jobid = re.sub(r'[^a-zA-Z0-9_]', '', arg)
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      if arg in ('tc', 'fc', 'ir', '4b', '5b', 'all'):
        mode = arg
      else:
        print "ERROR: -m|--mode must be tc|fc|ir|4b|5b|all"
        sys.exit(2)
    elif opt in ('-t', '--threshold'):
      threshold = arg
    elif opt in ('-s', '--shape'):
      shape = arg
    elif opt in ('-c', '--compact'):
      compact = arg
    elif opt in ('-v', '--verbose'):
      verbose = True

  if len(jobid) == 0:
    print "ERROR: -j|--jobid is a required parameter and only contain [a-zA-Z0-9_] charaters."
    sys.exit(1)

  if len(threshold) == 0 or len(shape) == 0 or len(compact) == 0:
    print "ERROR: -t|--threshold, -s|--shape, and -c|--compact are required!"
    sys.exit(1)

  l_threshold = threshold.split(',')
  l_shape = shape.split(',')
  l_compact = compact.split(',')

  # sanitize project so we don't inject any sql badness
  proj = re.sub(r'[^a-zA-Z0-9_]', '_', project)

  # for each set of t, s, c parameters
  # create a relevance table
  rtables = []
  modes = [mode]
  if mode == 'all':
    modes = allmodes
  for m in modes:
    for t in l_threshold:
      for s in l_shape:
        for c in l_compact:
          tabl = "%s_%s_%s_%02d_%02d_%02d" % \
                 ( jobid, proj, m, int(t), int(float(s)*10), int(float(c)*10) )
          rtables.append( tabl )
          print "Computing relevance for '%s'" % ( tabl )

          cmd = [ './prep-relevance.py', '-b', tabl, '-j', jobid,
                  '-m', m, '-t', t, '-s', s, '-c', c]
          if project != '':
            cmd = cmd + ['-p', project]

          if verbose:
            cmd.insert( 1, '-v' )
            print ' '.join( cmd )
            subprocess.call( cmd )
          else:
            subprocess.call( cmd, stdout=DEVNULL, stderr=subprocess.STDOUT )

  printRunSummary( rtables, verbose )




if __name__ == '__main__':

  if len(sys.argv) == 1:
    Usage()

  Main(sys.argv[1:])

