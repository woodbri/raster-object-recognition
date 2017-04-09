#!/usr/bin/env python
'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import sys
import getopt
import psycopg2
import subprocess



def Usage():
  print '''
Usage: eval-stats.py options
  options:
    [-h|--help]
    [-j|--jobid name]          - filter on this
    [-p|--project name]        - filter on this
    [-m|--mode ir|tc|fc|4b|5b] - filter on this
    [-f|--field pct|cov1|cov2] - select which stats to display
    [-o|--order min|max|avg|std] - order results by
    [--asc|--desc]             - direction of order by
    [--hist]                   - report histograms if field=pct
    [-g|--go]                  - report stats
'''
  sys.exit(2)


def Main(argv):

  jobid = '.*'
  project = '.*'
  mode = '..'
  field = 'pct'
  order = 'std'
  asc = True
  go = False
  histogram = False

  try:
    opts, args = getopt.getopt(argv, 'hj:p:m:f:o:g', ['help', 'jobid', 'project', 'mode', 'field', 'order', 'asc', 'desc','go', 'hist'])
  except:
    Usage()

  for opt, arg in opts:
    if opt in ('-h', '--help'):
      Usage()
    elif opt in ('-j', '--jobid'):
      jobid = arg
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      if arg in ('ir', 'tc', 'fc', '4b', '5b'):
        mode = arg
    elif opt in ('-f', '--field'):
      if arg in ('pct', 'cov1', 'cov2'):
        field = arg
      else:
        print "Invalid argument for field (%s)" % ( arg )
        Usage()
    elif opt in ('-o', '--order'):
      if arg in ('min','max','avg','std'):
        order = arg
      else:
        print "Invalid argument for order (%s)" % ( arg )
        Usage()
    elif opt == '--asc':
      asc = True
    elif opt == '--desc':
      asc = False
    elif opt == '--hist':
      histogram = True
    elif opt in ('-g', '--go'):
      go = True

  if not go:
    Usage()

  if jobid == '.*' and project == '.*' and mode == '..':
    clause = ''
  else:
    clause = "AND c.relname ~ '^(%s_%s_%s_.*)$'" % ( jobid, project, mode )

  sql = '''
SELECT c.relname as name
FROM pg_catalog.pg_class c
     LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname !~ '^pg_toast'
  %s
  AND n.nspname ~ '^(relevance)$'
ORDER BY 1''' % ( clause )

  try:
    conn = psycopg2.connect('dbname=ma_buildings')
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(2)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  cur.execute(sql)
  tables = cur.fetchall()

  obase = {'pct':4, 'cov1':8, 'cov2':12}
  stat  = {'min':0, 'max':1, 'avg':2, 'std':3}
  orderby = obase[field]+stat[order]

  if asc:
    direction = 'asc'
  else:
    direction = 'desc'

  parts = []
  for row in tables:
    parts.append('''select '%s' as tab, class, count(*),
    min(pctoverlap),
    max(pctoverlap),
    avg(pctoverlap),
    stddev(pctoverlap),
    min(coverage1),
    max(coverage1),
    avg(coverage1),
    stddev(coverage1),
    min(coverage2),
    max(coverage2),
    avg(coverage2),
    stddev(coverage2),
    sum(case when centr_seg then 1 else 0 end),
    sum(case when centr_trg then 1 else 0 end)
  from relevance."%s" group by class''' % ( row[0], row[0] ) )

  if len(parts) == 0:
    print "No tables to query!"
    sys.exit(2)

  sql = 'select * from (\n' + '\n union all \n'.join( parts ) + ' ) foo order by %d %s' % ( orderby, direction )
  cur.execute( sql )
  print "table\tclass\tcount\tminimum\tmaximum\taverage\tstddev\tcentr_seg\tcentr_trg"
  #print '----------------------------------------------------------------------'
  for r in cur:
    rr = r[:3]
    if field == 'pct':
      rr = rr + r[3:7] + r[-2:]
      fmt = "%s\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%d\t%d"
    elif field == 'cov1':
      # scale old value of cov1, now changed to ratio so no need to scale
      #rr = rr + tuple(map(lambda x: float(x)*1000000.0, r[7:11])) + r[-2:]
      rr = rr + r[7:11] + r[-2:]
      fmt = "%s\t%d\t%d\t%f\t%f\t%f\t%f\t%d\t%d"
    elif field == 'cov2':
      rr = rr + r[11:15] + r[-2:]
      fmt = "%s\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%d\t%d"
    print fmt % tuple(rr)
  #print '----------------------------------------------------------------------'

  conn.close()

  if histogram:
    fields = {'pct':'pctoverlap', 'cov1':'coverage1', 'cov2':'coverage2'}
    for tab in tables:
      sql = 'select class, width_bucket(%s, 0, 1.0, 9) as bucket, count(*) from "%s" group by 1,2 order by 1,2' % ( fields[field], tab[0] )
      print '----------------- ' + tab[0] + '-----------------------'
      print subprocess.check_output( ['psql', '-c', sql, 'ma_buildings'] )



if __name__ == '__main__':
  if len(sys.argv) == 1:
    Usage()
  Main(sys.argv[1:])
