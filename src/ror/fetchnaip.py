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
import getopt
import subprocess
from config import *
from utils import loadZippedShape

def reportNaipStatus(args):
    # report by year
    # what states we have shapes for
    # number of possible doqqs by state
    # number of doqqs downloaded by state
    # number of doqqs converted by state
    pass


def reportStatus(which, args):
    if which in ('naip', 'all'): reportNaipStatus(args)



def getLoadNaipShp(year, allStates):
    verbose = CONFIG.get('verbose', False)

    # get the template url
    urltpl = CONFIG['naip.url']['shp.url']

    # get values for the fields in the template
    yy = year[-2:]
    if allStates:
        states = FIPS2ST.values()
    else:
        states = [FIPS2ST[CONFIG['areaOfInterest'][:2]]]

    # define where the files will get put
    shpdir = os.path.join(CONFIG['projectHomeDir'], 'naip', year, 'shape')
    print 'shpdir:', shpdir
    if not os.path.exists( shpdir ):
        os.makedirs( shpdir )

    # loop through the list of states and fetch the files
    for st in states:
        url = urltpl.format(year, st, yy)
        print 'getLoadNaipShp:', url
        cmd = ['wget', '-o', shpdir + 'shapes.log',
               '-N', '-nv', '-nd', '-nH', '-P', shpdir, url]

        if verbose:
            print ' '.join(cmd)
        subprocess.call( cmd )

    zipfile = r'.*\.zip$'
    loadZippedShape( 'naip.naipbbox{}'.format(year), shpdir, zipfile )




def getNaipFiles(year, areaOfInterest):
    # create table if not exists to log downloaded DOQQs
    # query to get list of doqqs to fetch
    # loop through list and download them
    # mark them as downloaded

    pass



def FetchNaip( argv ):
    try:
        opts, args = getopt.getopt(argv, "y:a:", ['no-shp', 'no-naip', 'status', 'area'])
    except:
        return True # error occurred

    year = CONFIG['naip.url']['year']
    doshp = True
    donaip = True
    dostatus = False
    allStates = False
    areaOfInterest = ''

    for opt, arg in opts:
        if opt == '-y':
            year = arg
        elif opt == '--all-states':
            allStates = True
        elif opt == '--no-shp':
            doshp = False
        elif opt == '--no-naip':
            donaip = False
        elif opt == '--status':
            dostatus = True
        elif opt in ('-a', '--area'):
            areaOfInterest = opt

    if dostatus:
        reportStatus('naip', {'year':year})

    if not doshp and not donaip:
        print "Nothing to do!"
        return False

    if doshp:
        if getLoadNaipShp(year, allStates):
            print "WARNING: getLoadNaipShp got error(s)!"

    if donaip:
        # check we have shapes table
        # for doqqs in shapes table
        #   download file
        #   mark it as loaded in db
        if getNaipFiles(year, areaOfInterest):
            print "WARNING: getNaipFiles got error(s)!"

    return False # no errors


