#!/usr/bin/env python

import getopt
import psycopg2

flds = ['nbpixels',
        'meanb0', 'meanb1', 'meanb2', 'meanb3', 'meanb4', 'meanb5',
        'varb0', 'varb1', 'varb2', 'varb3', 'varb4', 'varb5',
        'area', 'perim', 'para', 'compact', 'compact2',
        'smooth', 'shape', 'frac', 'circle']


def Usage():
    print '''
Usage: getpolygonstats.py options
    options:
        [-h|--help]        - display help info
        [-d|--db 'dsn']    - database credentials
        [-t|--table table] - table to query
'''



def computeStats( dsn, table ):
    try:
        conn = psycopg2.connect( dsn )
    except:
        print "ERROR: computeStats could not connect to database"
        print "dsn:", dsn
        return None

    cur = conn.cursor()

    stats = {}

    for k in flds:
        sql = 'select min({0}), max({0}), avg({0}), stddev({0}) from {1}'.format( k, table )
        #print sql
        try:
            cur.execute( sql )
        except:
            continue

        stats[k] = cur.fetchone()

    conn.close()

    return stats



def Main(argv):

    try:
        from config import CONFIG
        dsn = CONFIG.get('dsn', '')
    except:
        dsn = ''

    try:
        opts, args = getopt.getopt(argv, "hd:t:", ['help', 'db', 'table'])
    except getopt.GetoptError:
        print 'ERROR in getpolygonstats options!'
        print 'args:', argv
        print getopt.GetoptError
        return True

    table = ''

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            return True
        elif opt in ('-d', '--db'):
            dsn = arg
        elif opt in ('-t', '--table'):
            table = arg

    if dsn == '' or table == '':
        print 'ERROR: both db and table are required!'
        return True

    stats = computeStats( dsn, table )
    if stats is None:
        return True


    print '   Field  |    Min   |    Max   |   Mean   |    Std   |'
    print '----------+----------+----------+----------+----------+'
    for k in flds:
        try:
            print ' {0:8s} | {1[0]:8f} | {1[1]:8f} | {1[2]:8f} | {1[3]:8f} |' \
                .format( k, stats[k] )
        except:
            pass
    print '----------+----------+----------+----------+----------+'

    return False



if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        Usage()
        sys.exit(2)

    if Main( sys.argv[1:] ):
        Usage()

