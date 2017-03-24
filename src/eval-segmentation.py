#!/usr/bin/env python

import os
import sys
import re
import getopt
import psycopg2
import subprocess
from buildings import getInfo

'''
  evaluate multiple t, s, c parameters of the segmentation process
  and try to pick the that gives up the best results

  for a given training set:
    * take 40% of the polygons and use them for training
    * take 40% of the polygons and use them for evaluation
    * save 20% of the polygons as a hold back set for final evaluation

  there are currently two proceses planned to do this:
  1. a short path:
     compute the relevance for all the polygons
     and try to increase the average mutual coverage
     and decrease the stddev on the average mutual coverage
     take the best 2-3 sets of parameters and run them through 2.

  2. a long path: (NOT IMPLEMENTED YET)
     compute the relevance for all the polygons
     create a trained classifier using the training polygons
     run the test polygons through the trained classifier
     evaluate the goodness of the fit

  In either case, save the parameters that gave the best fit.

  Relevance tables will be generated based on <jobid>_<project>_<T>_<S>_<C>
'''


def Usage():
  print '''
Usage: eval-segmentation.py options dir
    where options are:
      [-h|--help]          - display help message
      [-i|--info]          - display info about jobs and exit
      [-j|--jobid name]    - unique name for this job (required)
      [-p|--project name]  - unique project name for this job
      [-m|--mode mm]       - mm = tc|fc|ir|4b|5b|all
      [-t|--threshold T]   - T1[,T2,...] thresholds, required
      [-s|--shape S]       - S1[,S2,...] shape rate, required
      [-c|--compact C]     - C1[,C2,...] compact/smoothness, required
      [-l|--long]          - do the long path evaluation
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
      "select '%s' as tab, count(*) as count, avg(pctoverlap), stddev(pctoverlap) from %s" % ( t, t )
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
  do_info = False

  try:
    opts, args = getopt.getopt(argv, 'hij:p:m:t:s:c:lv', ['help', 'info', 'jobid', 'project', 'mode', 'threshold', 'shape', 'compact', 'long', 'verbose'])
  except:
    Usage()

  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    elif opt in ('-i', '--info'):
      do_info = True
    elif opt in ('-j', '--jobid'):
      jobid = re.sub(r'[^a-zA-Z0-9_]', '', arg)
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      if arg in ('tc', 'fc', 'ir', '4b', '5b', 'all'):
        mode = arg
      else:
        print "ERROR: -m|--mode must be tc|fc|ir|4b|all"
        sys.exit(2)
    elif opt in ('-t', '--threshold'):
      threshold = arg
    elif opt in ('-s', '--shape'):
      shape = arg
    elif opt in ('-c', '--compact'):
      compact = arg
    elif opt in ('-l', '--long'):
      longpath = True
    elif opt in ('-v', '--verbose'):
      verbose = True

  if do_info:
    getInfo(mode, jobid, project)

  if len(jobid) == 0:
    print "ERROR: -j|--jobid is a required parameter and only contain [a-zA-Z0-9_] charaters."
    sys.exit(1)

  if len(threshold) == 0 or len(shape) == 0 or len(compact) == 0:
    print "ERROR: -t|--threshold, -s|--shape, and -c|--compact are required!"
    sys.exit(1)

  if len(args) != 1:
    print "ERROR: extra args or missing 'dir' param!"
    sys.exit(1)

  if longpath:
    print "WARNING: long path evaluation is NOT implemented yet. Ignoring!"

  l_threshold = threshold.split(',')
  l_shape = shape.split(',')
  l_compact = compact.split(',')

  cmd = [ 'python', 'segment-dir.py', '--nostats', '--nolineup', '-t', threshold, '-s', shape, '-c', compact, args[0] ]
  if verbose:
    cmd.insert( 2, '-v' )
    print ' '.join( cmd )
    subprocess.call( cmd )
  else:
    subprocess.call( cmd, stdout=DEVNULL, stderr=subprocess.STDOUT )

  if project == '':
    cmd = ['./load-seg-data.py', jobid, args[0]]
  else:
    cmd = ['./load-seg-data.py', '-p', project, jobid, args[0]]
  if verbose:
    cmd.insert( 1, '-v' )
    print ' '.join( cmd )
    subprocess.call( cmd )
  else:
    subprocess.call( cmd, stdout=DEVNULL, stderr=subprocess.STDOUT )

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
                  '-m', m, '-t', threshold, '-s', shape, '-c', compact]
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

  #printRunSummary( ['evaltest_evaltest1_all_80_01_01'], True )
  #sys.exit(0)

  if len(sys.argv) == 1:
    Usage()

  Main(sys.argv[1:])


