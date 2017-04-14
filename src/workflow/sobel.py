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
import getopt
import psycopg2
import subprocess
import gdal
import re
import numpy as np

def createSobel( f_in, f_out ):
    from skimage import io
    from skimage.util import img_as_float
    from skimage.color import rgb2gray
    try:
        from skimage import filters
    except:
        from skimage import filter as filters

    ds = gdal.Open( f_in )
    gt = ds.GetGeoTransform()
    srs = ds.GetProjectionRef()

    #rgb = io.imread( f_in )
    #print "rgb", rgb.shape
    grey = io.imread( f_in, as_grey=True )
    #grey = rgb2gray(rgb)
    print "grey", grey.shape
    '''
    rgb = None
    grey = None

    #grey = io.imread( f_in, as_grey=True, plugin='gdal' )
    rgb = io.imread( f_in, plugin='gdal' )
    rgb = img_as_float(rgb)
    print 'gdal:rgb', rgb.shape
    #aa = np.moveaxis(rgb, 0, -1)
    rgb = rgb.transpose(1, 2, 0)
    print 'gdal:rgb:moveaxis', rgb.shape
    #grey = rgb2gray(rgb[:,:,:3])
    grey = rgb2gray(rgb)
    print 'gdal:grey', grey.shape
    io.imsave( 'gray.tif', grey )
    '''

    im_sobel = filters.sobel( grey )
    io.imsave( f_out, im_sobel )

    # add georeferencing to image
    sb_ds = gdal.Open( f_out, gdal.GA_Update )
    sb_ds.SetGeoTransform( gt )
    sb_ds.SetProjection( srs )
    sb_ds = None


def Main():
    if len(sys.argv) == 1:
        print "Usage: sobel.py file.tif [sobel.tif]"
        sys.exit(1)

    sobel = 'sobel.tif'
    if len(sys.argv) == 3:
        sobel = sys.argv[2]

    createSobel( sys.argv[1], sobel )

if __name__ == '__main__':
    Main()
