'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import sys
import psycopg2
#from config import *

CONFIG = {
    # set verbose for debugging
    'verbose': True,

    # set nproc to number of processes to use
    # set to 0 to use all cpus
    'nproc': 0,

    # set the home directory for this project
    'projectHomeDir': '/u/ror/buildings',

    # set the database connection parameters
    'dbname': 'buildings',
    'dbuser': 'postgres',
    'dbhost': 'localhost',
    'dbport': '5435',
    'dbpass': '',

    # set the number of cpu's to use for processing
    # this can be commented out and the system
    # will check how many cpu's are available
    # on Mac OSX you should set this value as appropriate
    # otherwise it will default to 1
    #'ncpu': 4,

    # configure tmp dirs
    # if you have multiple disks, you can configure multiple
    # tmp dirs, one on each disk
    # during some multi-processing we can spread the work over
    # these tmps dirs to reduce disk I/O contension
    # the default location if not configured is
    # 'projectHomeDir'/tmp/
    'tmpdirs':['/u/ror/buildings/tmp/'],

    # Area Of Interest can be defined as:
    # bbox with [xmin, ymin, xmax, ymax]
    # or as US Census FIPS string like 'ss|ssccc|sscccnnnnn'
    # where ss = state code
    #       ccc = county code
    #       nnnnn = county sub-division code
    #'areaOfInterest': [],
    'areaOfInterest': '06',

    # define the year we are working with
    'year': '2014',

    # ----------------- census support data ---------------------

    # set the urls for fetch the census files
    # set census.url = '' to disable this feature
    'census.url': 'ftp://ftp2.census.gov/geo/tiger/TIGER%s/',
    'census.year': '2016',
    'census.layers': {
        'roads':  ['ROADS',  'tl_%s_%s_roads.zip'],
        'county': ['COUNTY', 'tl_%s_us_county.zip'],
        'cousub': ['COUSUB', 'tl_%s_%s_cousub.zip']
    },

    # ----------------- NAIP DOQQ Resources ----------------------

    # set the urls for fetching NAIP imagery
    'naip.url': {
        'shp.url': 'https://www.fsa.usda.gov/Assets/USDA-FSA-Public/usdafiles/APFO/imagery-programs/zips/naip/{0}/{1}_naip{2}qq.zip',
        # where {0} = YEAR, {1} = st abbrev lowercase, {2} = YY year
        'doqq.urls': {
            '2016':'',
            '2015':'',
            '2014':'http://atlas.ca.gov/casil/imageryBaseMapsLandCover/imagery/naip/naip2014/NAIP_2014_DOQQ/Data/TIFF/{0}/{1}'
            # for 2014: where {0} = filename[2:7], {1} = filename[:26] + '.tif'
            }
    },

    # ----------------- Misc NAIP processing info ------------------

    'naip.projection': 'EPSG:4326',
    'naip.download': 'data/naip/download',
    'naip.doqq_dir': 'data/naip/doqqs',
    'naip.shapefile': 'data/naip/shapefile',
    'naip.shptable': 'naipbbox{0}',         # {0} - year
    'naip.sobel': False,

    # ----------------- OSM building data --------------------------

    # set the url and optional bbox for OSM data
    'osm.url': None,
    'osm.bbox': None,

    # ---------------- Segmentation paramaters ----------------------

    'seg.ram': 8192,    # (int) available ram for processing in MB
    'seg.spatialr': 16, # (int) Spatial radius (Hs) of neighborhood pixels
    'seg.ranger': 16,   # (float) Range radius (Hr) in radiometry units in
                        # in the multi-spectral space
    'seg.minsize': 100, # (int) minimum size of segment (M) (pixels)
                        # smaller segments will get merged to closest
                        # similar adjacent segment
    'seg.thresh': 0.1,  # (float) mode convergence threshold
    'seg.rangeramp': 0, # (float) ranger radius coefficient where:
                        #       y = ramgeramp*x+ranger
    'seg.max-iter': 100,# (int) max number of iterations to convergence
    'seg.tilesize': 1024,    # size of tiles used in processing
    'seg.shapedir': 'data/segments',
    'seg.table': 'segments.y{0}_{1}', # {0}= year, {1}= jobname

    # ---------------- end of config data ----------------------------
    'EOF': True
    }

FIPS2ST = {
    '01':'al', '02':'ak', '60':'as', '03':'as', '04':'az',
    '05':'ar', '06':'ca', '08':'co', '09':'ct', '10':'de',
    '11':'dc', '12':'fl', '64':'fm', '13':'ga', '66':'gu',
    '15':'hi', '16':'id', '17':'il', '18':'in', '20':'ks',
    '21':'ky', '22':'la', '23':'me', '68':'mh', '24':'md',
    '25':'ma', '27':'mn', '28':'ms', '29':'mo', '30':'mt',
    '31':'ne', '32':'nv', '33':'nh', '34':'nj', '35':'nm',
    '36':'ny', '37':'nc', '38':'nd', '69':'mp', '39':'oh',
    '40':'ok', '41':'or', '70':'pw', '42':'pa', '72':'pr',
    '44':'ri', '45':'sc', '46':'sd', '47':'tn', '48':'tx',
    '49':'ut', '50':'vt', '51':'va', '78':'vi', '53':'wa',
    '54':'wv', '55':'wi', '56':'wy'
    }

def checkConfig():
    dsn = ["dbname=%s" % (CONFIG['dbname'])]
    if CONFIG.get('dbhost', '') != '':
        dsn.append("host=%s" % (CONFIG.get('dbhost')))
    if CONFIG.get('dbport', '') != '':
        dsn.append("port=%s" % (CONFIG.get('dbport')))
    if CONFIG.get('dbuser', '') != '':
        dsn.append("user=%s" % (CONFIG.get('dbuser')))
    if CONFIG.get('dbpass', '') != '':
        dsn.append("pass=%s" % (CONFIG.get('dbpass')))

    #print "DSN:", ' '.join(dsn)
    CONFIG['dsn'] = ' '.join(dsn)
    try:
        conn = psycopg2.connect( CONFIG['dsn'] )
    except:
        pass
    if conn is None:
        print "ERROR: checkConfig could not connect to database"
        sys.exit(1)
    else:
        conn.close()

    # additional checks can be added here to make sure reasonable
    # defaults are assigned and that all critial variables exist
    # TODO


checkConfig()
