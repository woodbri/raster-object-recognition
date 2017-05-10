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
import math
import numpy as np
from scipy import ndimage
from scipy.stats import norm
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
from osgeo import gdal
try:
    from config import *
except:
    CONFIG = {'verbose': False}

#gdal.UseExceptions()


def semivariogram( ds, band, lag ):
    '''
    semivariogram( ds, band, lag )

    This function computes semivariance [Horizontal variance, Vertical variance,
    Average of Horizontal and Vertical variances] of a given band in
    the given image (ds) for the given lag.

    Reference:
    Semivariogram-Based Spatial Bandwidth Selection for Remote Sensing Image
    Segmentation With Mean-Shift Algorithm, 2012, by Dongping Ming, Tianyu Ci,
    Hongyue Cai, Longxiang Li, Cheng Qiao, and Jinyang Du

    '''
    width = ds.RasterXSize
    height = ds.RasterYSize
    data = band.ReadAsArray( 0, 0, width, height ).astype(np.float)

    '''
    # the follow is a conversion of the loops to python slices
    # to improve performace, For more information, see:
    # http://stackoverflow.com/questions/43813986/how-to-use-numpy-and-strides-to-improve-performance-of-loop

    print "lag:", lag

    sumw = 0.0
    sumh = 0.0
    for i in range(width-lag):
        for j in range(height-lag):
            sumw += (data[i+lag,j]-data[i,j])**2
            sumh += (data[i,j+lag]-data[i,j])**2

    print 0, sumw, sumh

    sumw = 0.0
    for i in range(width-lag):
        for j in range(height-lag):
            sumw += (data[i+lag,j]-data[i,j])**2
    sumh = 0.0
    for j in range(height-lag):
        for i in range(width-lag):
            sumh += (data[i,j+lag]-data[i,j])**2

    print 1, sumw, sumh

    sumw = 0.0
    for i in range(width-lag):
        for j in range(height-lag):
            sumw += (data[lag:,:][i,j]-data[:-lag,:][i,j])**2
    sumh = 0.0
    for j in range(height-lag):
        for i in range(width-lag):
            sumh += (data[:,lag:][i,j]-data[:,:-lag][i,j])**2

    print 2, sumw, sumh

    sumw = ((data[lag:,:-lag] - data[:-lag,:-lag])**2).sum()
    sumh = ((data[:-lag,lag:] - data[:-lag,:-lag])**2).sum()

    print 3, sumw, sumh
    '''

    shared_term = data[:-lag,:-lag]
    sumw = ((data[lag:,:-lag] - shared_term)**2).sum()
    sumh = ((data[:-lag,lag:] - shared_term)**2).sum()

    #print 4, sumw, sumh

    Nh2 = 2.0*(width-lag)*(height-lag)

    return [sumw/Nh2, sumh/Nh2, (sumw/Nh2+sumh/Nh2)/2.0]


def getOptimalSV( b, data, drange, verbose, plotit ):
    '''
    getOptimalSV( b, data, drange, verbose, plotit )

        b       - band number (used for title on plots
        data    - synthetic variance for each successive lag
        drange  - [start, end, step] the range of lag values
        verbose - bool flag to trigger additional prints
        plotit  - bool flag to generate and display plots

    Reference:
    Semivariogram-Based Spatial Bandwidth Selection for Remote Sensing Image
    Segmentation With Mean-Shift Algorithm, 2012, by Dongping Ming, Tianyu Ci,
    Hongyue Cai, Longxiang Li, Cheng Qiao, and Jinyang Du

    '''
    optw = None
    opth = None
    opta = None
    minw = None
    minh = None
    mins = None
    y = []
    for i in range(1,len(data)):
        #print data[i], data[i-1]
        dw = data[i][0] - data[i-1][0]
        dh = data[i][1] - data[i-1][1]
        da = data[i][2] - data[i-1][2]
        y.append(da)
        if optw is None and dw <= 0.0:
            optw = i*drange[2]+drange[0]
        if minw is None or dw < minw[0]:
            minw = [dw, i*drange[2]+drange[0]]
        if opth is None and dh <= 0.0:
            opth = i*drange[2]+drange[0]
        if minh is None or dh < minh[0]:
            minh = [dh, i*drange[2]+drange[0]]
        if opta is None and da <= 0.0:
            opta = i*drange[2]+drange[0]
        if mins is None or da < mins[0]:
            mins = [da, i*drange[2]+drange[0]]

    if optw is None and not minw is None:
        optw = minw[1]
    if opth is None and not minh is None:
        opth = minh[1]
    if opta is None and not mins is None:
        opta = mins[1]

    if plotit:
        x = range(drange[0], drange[1], drange[2])
        x.pop()
        plt.xlabel('Lag (h)(pixel)')
        plt.ylabel('Increase of synthetic semivariance')
        plt.title('Band {}'.format(b))
        plt.plot(x,y,'r')
        plt.show()

    return [optw, opth, opta]


def getOptimalHs( ds, useBands, drange, verbose, plotit ):
    '''
    getOptimalHs( ds, useBands, drange, verbose, plotit )
        ds       - gdal dataset reference for the image
        useBands - list of bands to evaluate
        drange   - [start, end, step] for lags to evaluate
        verbose  - bool flag to turn on additional prints
        plotit   - bool flag to generate and display plots

    Compute the optimal spatial bandwidth based on the semivariogram
    of the image.

    Reference:
    Semivariogram-Based Spatial Bandwidth Selection for Remote Sensing Image
    Segmentation With Mean-Shift Algorithm, 2012, by Dongping Ming, Tianyu Ci,
    Hongyue Cai, Longxiang Li, Cheng Qiao, and Jinyang Du

    '''
    data = []
    opt_hs = []

    ii = 0
    for b in range(ds.RasterCount):
        b1 = b + 1
        band = ds.GetRasterBand( b1 )
        if band is None or not b in useBands:
            continue
        stats = band.GetStatistics( True, True )
        if stats is None:
            continue

        if verbose:
            print "STATS({}): min: {}, max: {}, mean: {}, stddev: {}".format(
                b, stats[0], stats[1], stats[2], stats[3] )

        # create a slot we can add sv data to
        data.append([])
        for lag in range(drange[0], drange[1], drange[2]):
            sv = semivariogram( ds, band, lag )
            data[ii].append(sv)

        opt = getOptimalSV( b1, data[ii], drange, verbose, plotit )
        opt_hs.append(opt[2])
        if verbose:
            print 'Band {}: optimal h: {}'.format(b1, opt)

        if plotit:
            x = range(drange[0], drange[1], drange[2])
            y1 = [ y[0] for y in data[ii] ]
            y2 = [ y[1] for y in data[ii] ]
            y3 = [ y[2] for y in data[ii] ]
            plt.xlabel('Lag (h)(pixel)')
            plt.ylabel('Semivariance')
            plt.title('Band {}'.format(b1))
            plt.plot(x,y1,'r',x,y2,'g',x,y3,'b--')
            plt.show()

        ii += 1

    hs_min = int(round(min(opt_hs)))
    hs_max = int(round(max(opt_hs)))
    hs_avg = int(round(sum(opt_hs)/len(opt_hs)))

    return (hs_min, hs_max, hs_avg)


def getOptimalHr( ds, useBands, winsize, verbose, plotit ):
    '''
    getOptimalHr( ds, useBands, winsize, verbose, plotit )
        ds       - gdal dataset image reference
        useBands - list of bands to consider
        winsize  - window size for local variance
        verbose  - bool flag to print messages
        plotit   - bool flag to generate and show plots

    Compute the optimal spectral resolution for the given windsize
    that was returned from getOptimalHs function. This is done by
    create a local variance (LV) image derived from the image (ds)
    and then fitting a curve through the histogram of the LV image.

    Reference:
    Scale parameter selection by spatial statistics for GeOBIA: Using
    mean-shift based multi-scale segmentation as an example, 2015,
    Dongping Ming, Jonathan Li, Junyi Wang, Min Zhang

    '''

    opt_hr = []

    for b in range(ds.RasterCount):
        b1 = b + 1
        band = ds.GetRasterBand( b1 )
        if band is None or not b in useBands:
            continue

        img = np.array( band.ReadAsArray().astype(np.int) )

        data = [] # the LV image

        # eval a sliding window of winsize over the image
        # and calculate the local variance of each pixel
        # based on the neighborhood of the window
        #
        # this uses: the variance is the difference between "sum of square"
        # and "square of sum" which might have numerical issues if the
        # values are vary large and the differences are very small
        # but since we are working with values between 0-255 it should not
        # be a problem.

        win_mean = ndimage.uniform_filter( img, (winsize, winsize) )
        win_sqr_mean = ndimage.uniform_filter( img**2, (winsize, winsize) )
        win_var = win_sqr_mean - win_mean**2
        data.append( win_var )
        alv = np.mean(np.array(data))

        # fit the data to gausian curve and select hr
        # from where the curve peaks
        #
        # in theory we want the first non false peak as
        # it is possible to multiple peaks but for now
        # we fit it to a gausian curve which has a single peak

        tmp = np.array( data )
        (mu, sigma) = norm.fit(tmp.ravel())

        opt_hr.append( math.sqrt(mu) )

        if plotit:
            bits_per_pixel = 8
            nbins = 2**bits_per_pixel / 4
            n, bins, patches = plt.hist( tmp.ravel(), nbins, normed=1 )

            # add a 'best fit' line
            y = mlab.normpdf( bins, mu, sigma)
            l = plt.plot(bins, y, 'r--', linewidth=2)
            plt.title("Histogram of Band {} Local Variance".format(b1))
            plt.show()


    hr_min = int(round(min(opt_hr)))
    hr_max = int(round(max(opt_hr)))
    hr_avg = int(round(sum(opt_hr)/len(opt_hr)))

    return (hr_min, hr_max, hr_avg)



def getOptimalParameters( boxy, infile, useBands, verbose, plotit ):
    '''
    getOptimalParameters( boxy, infile, useBands, verbose, plotit )
        boxy     - bool flag if segments are boxy (square or rectangle)
        infile   - name of input file to evaluate
        useBands - list of bands to consider
        verbose  - bool flag to print messages
        plotit   - bool flag t0 generate and display plots

    returns a dictionary of results with keys for:
        hs_min, hs_max, hs_avg - spatial resolution
        hr_min, hr_max, hr_avg - spectral resolution
        M_min, M_max, M_avg    - minimum segment size

    Main public interface that evaluates an image and reports the optimal
    parameters for mean-shift segmentation.
    '''
    if plotit:
        import matplotlib.pyplot as plt
        import matplotlib.mlab as mlab

    ds = gdal.Open( infile )

    factor = 4
    if boxy: factor = 2

    # range parameters for search [2, 100, 2] => 2 through 100 by 2
    drange = [2, 100, 2]

    hs_min, hs_max, hs_avg = getOptimalHs( ds, useBands, drange, verbose, plotit )
    hr_min, hr_max, hr_avg = getOptimalHr( ds, useBands, hs_avg, verbose, plotit )
    M_min = int(round(hs_min**2/factor))
    M_max = int(round(hs_max**2/factor))
    M_avg = int(round(hs_avg**2/factor))

    ds = None

    return { 'hs_min': hs_min, 'hs_max': hs_max, 'hs_avg': hs_avg,
             'hr_min': hr_min, 'hr_max': hr_max, 'hr_avg': hr_avg,
             'M_min':  M_min, 'M_max':  M_max, 'M_avg':  M_avg }


def Usage():
    print """
Usage: optimalparameters.py options"
where options:
    [-h|--help]
    [-f|--file infile]     - optional file to evaluate
    [-i|--isboxy=1|0]      - are objects square|rectangle or not, default: 1
                             1 - objects are squares or rectangles
                             0 - objects are not squares or rectangles
    [-b|--bands 0,1,2,4]   - which bands to use, zero based numbers
                             default: 0,1,2,4  (R,G,B,IR)
    [-p|--plots]           - display graph plots of data
    [-v|--verbose]         - print debug info
"""
    sys.exit(1)


def Main( argv ):
    import getopt

    boxy = True
    plotit = False
    verbose = CONFIG.get('verbose', False)
    useBands = [0,1,2,4]
    infile = None
    area = None

    try:
        opts, args = getopt.getopt(argv, "hf:i:b:pv", ['help', 'file', 'isboxy', 'bands', 'plots', 'verbose'])
    except:
        Usage()

    #print 'opts:', opts
    #print 'args:', args

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            Usage()
        elif opt in ('-f', '--file'):
            infile = arg
        elif opt in ('-i', '--isboxy'):
            boxy = arg != '0'
        elif opt in ('-b', '--bands'):
            bands = [int(i) for i in arg.split(',')]
        elif opt in ('-p', '--plot', '--plots'):
            plotit = True
        elif opt in ('-v', '--verbose'):
            verbose = True

    if infile is None:
        print "\nERROR: file is required"
        Usage()

    opt = getOptimalParameters( boxy, infile, useBands, verbose, plotit )

    print "   Optimal Parameters    "
    print "    |  Hs  |  Hr  |   M  "
    print "----+------+------+------"
    print "min |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_min'], opt['hr_min'], opt['M_min'])
    print "max |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_max'], opt['hr_max'], opt['M_max'])
    print "avg |  {0:2d}  |  {1:2d}  | {2:4d} ".format(opt['hs_avg'], opt['hr_avg'], opt['M_avg'])
    print "----+------+------+------"


if __name__ == '__main__':
    if len(sys.argv) == 1:
        Usage()

    Main( sys.argv[1:] )
