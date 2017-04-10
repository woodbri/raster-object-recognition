

from config import *
from utils import getDatabase


def reportNaipStatus(args):
    conn, cur = getDatabase()

    # report for year
    year = args.get('year', CONFIG['naip.url']['year'])

    # number of possible doqqs by state
    sql = 'select st, count(*) from naipbbox{} group by st order by st'.format(year)
    cur.execute( sql )

    print
    print 'Number of potential DOQQs by state for {}'.format(year)
    print '-------------------------------------------'
    for row in cur:
        print ' {0:>4s} | {1:8,d}'.format(row[0], row[1])
    print

    # number of doqqs downloaded by state
    sql = '''select st, count(*)
        from naipbbox{0} a
        left outer join naipfetched{0} b on a.gid=b.gid
        where b.gid is not null group by st order by st'''.format(year)
    cur.execute( sql )

    print 'Number of downloaded DOQQs by state for {}'.format(year)
    print '-------------------------------------------'
    for row in cur:
        print ' {0:>4s} | {1:8,d}'.format(row[0], row[1])
    print

    # TODO number of doqqs converted by state

    conn.close()


def reportStatus(which, args):
    if which in ('naip', 'all'): reportNaipStatus(args)



