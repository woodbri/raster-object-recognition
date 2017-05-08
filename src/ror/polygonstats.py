#!/usr/bin/env python
'''
--------------------------------------------------------------------
    This file is part of the raster object recognition project.

    https://github.com/woodbri/raster-object-recognition

    MIT License. See LICENSE file for details.

    Copyright 2017, Stephen Woodbridge
--------------------------------------------------------------------
'''

import math
from osgeo import ogr
from minboundingcircle import getCircle

class PolygonStats:
    """
    Class PolygonStats

    Computes metrics on a polygon. Many of these metrics are based on 
    FRAGSTATS metrics that are raster based metrics used to charactorize
    patches of pixels in a landscape.

    http://www.umass.edu/landeco/research/fragstats/documents/Metrics/Metrics%20TOC.htm

    from polygonstats import PolygonStats
    s = PolygonStats('POLYGON ((0 0,1 0,1 1,0 1,0 0))')
    """
    _geom = None
    _area = None
    _perim = None
    _bbarea = None
    _bbperim = None
    _circle = None # [x, y, radius]

    def __init__(self, geom_in):
        if type(geom_in) is str:
            self._geom = ogr.CreateGeometryFromWkt(geom_in)
        elif type(geom_in) is ogr.Geometry:
            self._geom = geom_in
        else:
            raise RuntimeError("Unknown geometry Syntax!")

        if self._geom.GetGeometryType() != 3:
            raise RuntimeError("Geometry is not a POLYGON!")

        # initialize attributes
        self._area = self._geom.Area()
        self._perim = ogr.ForceToMultiLineString(self._geom).Length()
        xmin, xmax, ymin, ymax = self._geom.GetEnvelope()
        dx = xmax - xmin
        dy = ymax - ymin
        self._bbperm = 2.0*(dx + dy)
        self._bbarea = dx * dy
        self._circle = getCircle(self._geom.GetGeometryRef(0).GetPoints())

    def getPoints(self):
        """Return a list of points from a polygon geometry"""
        gg = ogr.ForceToMultiLineString(self._geom)
        return gg.GetGeometryRef(0).GetPoints()

    def area(self):
        """Return polygon area (FRAGSTATS P4 AREA)"""
        return self._area

    def perim(self):
        """Return polygon perimeter (FRAGSTATS P5 PERIM)"""
        return self._perim

    def para(self):
        """Return polygon perimeter-area ratio (FRAGSTATS P7 PARA)"""
        if self._area > 0.0:
            return self._perim / self._area
        else:
            return 0.0

    def compact(self):
        """Return polygon compactness. A ratio of the polygons area
        to the area of the minimum circumscribed circle."""
        if self._circle is None:
            return None
        else:
            return self._area / (2.0 * math.pi * self._circle[2])

    def compact2(self):
        """
        Return polygon alternate compactness metric.
        http://en.wikipedia.org/wiki/Compactness_measure_of_a_shape
        """
        return 4.0 * math.pi * self._area / math.pow(self._perim, 2.0)

    def smooth(self):
        """Return polygon smoothness metric. A ratio of polygon perimeter
        to the perimeter of the minimum circumscribed circle."""
        if self._circle is None:
            return None
        else:
            return self._perim / (math.pi * math.pow(self._circle[2], 2.0))

    def shape(self):
        """Return polygon shape index (FRAGSTATS P2 SHAPE)
        Based on Shape Index from FRAGSTATS ver 4.2
        http://www.umass.edu/landeco/research/fragstats/documents/fragstats.help.4.2.pdf
        """
        return 0.25 * self._perim / math.sqrt(self._area)


    def frac(self):
        """Return polygon fractal dimension index (FRAGSTATS P9 FRAC)"""
        perim = self._perim / 4.0
        if self._area <= 1 or perim < 1:
            return 1.0
        else:
            return 2.0 * math.log(perim) / math.log(self._area)

    def circle(self):
        """Return polygon circluarity ratio (FRAGSTATS P11 CIRCLE)"""
        if self._circle is None:
            return None
        else:
            return 1.0 - self._area / (math.pi * math.pow(self._circle[2], 2))

    def getAllStatsList(self):
        """
        Return list of all metrics related to polygon.
        [area, perim, para, compact, compact2, smooth, shape, frac, circle]
        """
        return [ self.area(),
                 self.perim(),
                 self.para(),
                 self.compact(),
                 self.compact2(),
                 self.smooth(),
                 self.shape(),
                 self.frac(),
                 self.circle() ]


    def getAllStatsDict(self):
        """
        Return dictionary of all metrics related to polygon. With keys:
        area, perim, para, compact, compact2, smooth, shape, frac, circle
        """
        return { 'area':     self.area(),
                 'perim':    self.perim(),
                 'para':     self.para(),
                 'compact':  self.compact(),
                 'compact2': self.compact2(),
                 'smooth':   self.smooth(),
                 'shape':    self.shape(),
                 'frac':     self.frac(),
                 'circle':   self.circle() }


def addShapefileStats(shapefile):
    '''Read a polygon shapefile, compute stats, and add them to the shapefile.'''
    # open the shapefile
    driver = ogr.GetDriverByName('ESRI Shapefile')
    dataSource = driver.Open(shapefile, 1)
    if dataSource is None:
        print "ERROR: could not open '{}' as shapefile!".format(shapefile)
        sys.exit(1)

    layer = dataSource.GetLayer()
    layer.CreateField(ogr.FieldDefn("area",     ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("perim",    ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("para",     ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("compact",  ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("compact2", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("smooth",   ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("shape",    ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("frac",     ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("circle",   ogr.OFTReal))

    for feature in layer:
        geom = feature.GetGeometryRef()
        ps = PolygonStats( geom )
        stats = ps.getAllStatsList()
        if not stats[0] is None:
            feature.SetField("area",     stats[0])
        if not stats[1] is None:
            feature.SetField("perim",    stats[1])
        if not stats[2] is None:
            feature.SetField("para",     stats[2])
        if not stats[3] is None:
            feature.SetField("compact",  stats[3])
        if not stats[4] is None:
            feature.SetField("compact2", stats[4])
        if not stats[5] is None:
            feature.SetField("smooth",   stats[5])
        if not stats[6] is None:
            feature.SetField("shape",    stats[6])
        if not stats[7] is None:
            feature.SetField("frac",     stats[7])
        if not stats[8] is None:
            feature.SetField("circle",   stats[8])
        layer.SetFeature(feature)
        feature = None

    dataSource = None



def runTests():
    """Run unit tests."""

    def run_test(poly, test):
        """Run test and return True if errors"""
        g = PolygonStats( poly )
        header = True
        for k in test:
            ret = eval('g.'+k)()
            if abs(ret - test[k]) > 0.00000001:
                if header:
                    print 'Errors for %s:' % (poly)
                    header = False
                print '    g.%s(): = %.17f, expected: %.17f' % (k, ret, test[k])
        print
        return not header

    test = {'area':     1.0,
            'perim':    4.0,
            'para':     4.0,
            'compact':  0.22507907903927651,
            'compact2': 0.78539816339744828,
            'smooth':   2.54647908947032464,
            'shape':    1.0,
            'frac':     1.0,
            'circle':   0.36338022763241884 }
    err = run_test('POLYGON ((0 0,1 0,1 1,0 1,0 0))', test)


    test = {'area':     8.0,
            'perim':    16.0,
            'para':     2.0,
            'compact':  0.60021087743807078,
            'compact2': 0.39269908169872414,
            'smooth':   1.13176848420903386,
            'shape':    1.41421356237309492,
            'frac':     1.33333333333333348,
            'circle':   0.43411575789548307 }
    err = err or run_test('POLYGON ((0 0,3 0,3 3,0 3,0 0), (1 1,2 1,2 2,1 2,1 1))', test)

    if err:
        print 'Unit tests generated errors!'
    else:
        print 'Unit tests passed!'


def Usage():
    print '''
Usage: polygonstats.py options
    options:
        [-h|--help]  - display help info
        [-t|--test]  - run unit tests
        file.shp     - add polygon stats to shapfile
'''


if __name__ == '__main__':
    import sys

    if len(sys.argv) == 2 and sys.argv[1] in ('-h', '--help'):
        help(PolygonStats)
        Usage()

    elif len(sys.argv) == 2 and sys.argv[1] in ('-t', '--test'):
        runTests()

    elif len(sys.argv) == 2:
        addShapefileStats( sys.argv[1] )
    else:
        Usage()

