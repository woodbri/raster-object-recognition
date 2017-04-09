'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import psycopg2
from config import *

def InitDB():
    try:
        conn = psycopg2.connect( CONFIG['dsn'] )
    except:
        print "ERROR: failed to connect to database!"
        sys.exit(1)

    #conn.set_session(autocommit=True)
    cur = conn.cursor()

    cur.execute("set search_path to public")
    cur.execute("create extension if not exists postgis with schema public")
    cur.execute("create schema if not exists census")
    cur.execute("create schema if not exists data")
    cur.execute("create schema if not exists segments")
    cur.execute("create schema if not exists training")
    cur.execute("create schema if not exists search")
    cur.execute("create schema if not exists naip")
    cur.execute('alter database "%s" set search_path to data, census, naip, segments, training, search, public' % (CONFIG['dbname']))

    conn.commit()
    conn.close()

    print "Done"


