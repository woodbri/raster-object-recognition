#!/usr/bin/env python

import sys
import math
import random

'''
Welzl's Algorithm

* let mc(P) denote the min enclosing circle enclosing points P
* mc(P) for a given set P of n points is calculated in random
  incremental fashion
* let P be the set of n points and D = mc{p1, p2, ..., pn}
  a<=i<=n points seen so far
* now if pi+1 is in D, then append pi+1 to D
* else, we use the fact that pi+1 will lie on boundary of
  D' = mc{p1, p2, ..., pi, pi+1}
* we compute it calling mc1(A, p), which calculates the
  smallest circle enclosing A = {p1, p2, ..., pi} with
  p = pi+1 on its boundary
'''

def getCircle(points):
    '''
    [cx, cy, radius] = getCircle(points)
    
    Returns list defining minimum bounding circle for a list of points
    or None on failure
    '''

    # algorithm calls for randomized insertion of pnts
    pnts = [(float(p[0]), float(p[1])) for p in points]
    random.shuffle(pnts)

    #return _mec(pnts, len(pnts), [])
    bnd = [None, None, None]
    try:
        D = minidisk(pnts, len(pnts), bnd, 0)
    except:
        D = None
    return D


def minidisk(pt, np, bnd, nb):
    #print 'minidisk: np: {}, nb: {}'.format(np, nb)
    if np == 1:
        if nb == 0:
            return _calcCircle1(pt[0])
        elif nb == 1:
            return _calcCircle2([pt[0], bnd[0]])
    elif np == 0:
        if nb == 1:
            return _calcCircle1(bnd[0])
        elif nb == 2:
            return _calcCircle2([bnd[0], bnd[1]])
    if nb == 3:
        return _calcCircle3([bnd[0], bnd[1], bnd[2]])
    D = minidisk(pt, np-1, bnd, nb)
    dx = pt[np-1][0]-D[0]
    dy = pt[np-1][1]-D[1]
    dist2 = dx*dx + dy*dy
    if dist2 <= D[2]*D[2]:
        return D
    bnd[nb] = pt[np-1]
    nb = nb + 1
    return minidisk(pt, np-1, bnd, nb)


def _calcCircle3(pnts):
    p1x = pnts[0][0]
    p1y = pnts[0][1]
    p2x = pnts[1][0]
    p2y = pnts[1][1]
    p3x = pnts[2][0]
    p3y = pnts[2][1]

    dx = p1x-p2x
    dy = p1y-p2y
    a = math.sqrt(dx*dx + dy*dy)

    dx = p2x-p3x
    dy = p2y-p3y
    b = math.sqrt(dx*dx + dy*dy)

    dx = p3x-p1x
    dy = p3y-p1y
    c = math.sqrt(dx*dx + dy*dy)

    s = (a + b + c)*0.5
    denom = math.sqrt(s*(s-a)*(s-b)*(s-c))
    #if denom == 0:
    #    print 'denom==0'
    #    print 'pnts:', pnts
    #    print 'a: {}, b: {}, c: {}, s: {}'.format(a, b, c, s)
    #    sys.exit(1)
    r = a*b*c*0.25/denom

    t1 = p1x*p1x + p1y*p1y
    t2 = p2x*p2x + p2y*p2y
    t3 = p3x*p3x + p3y*p3y
    denom = 2.0*(p1x*(p2y-p3y) + p2x*(p3y-p1y) + p3x*(p1y-p2y))
    #if denom == 0:
    #    print 'denom==0'
    #    print 'pnts:', pnts
    #    print 't1: {}, t1: {}, t3: {}'.format(t1, t2, t3)
    #    sys.exit(1)
    
    cx = (t1*(p2y-p3y) + t2*(p3y-p1y) + t3*(p1y-p2y))/denom
    cy = (t1*(p3x-p2x) + t2*(p1x-p3x) + t3*(p2x-p1x))/denom

    C = [cx, cy, r]
    #print '_calcCircle3:', C
    return [cx, cy, r]

def _calcCircle2(pnts):
    p1x = pnts[0][0]
    p1y = pnts[0][1]
    p2x = pnts[1][0]
    p2y = pnts[1][1]

    cx = (p1x+p2x)*0.5
    cy = (p1y+p2y)*0.5

    dx = p1x-p2x
    dy = p1y-p2y

    C = [cx, cy, math.sqrt( dx*dx + dy*dy )*0.5]
    #print '_calcCircle2:', C
    return C

def _calcCircle1(pnts):
    p1x = pnts[0]
    p1y = pnts[1]

    C = [p1x, p1y, 0.0]
    #print '_calcCircle1:', C
    return C

def _test():
    p1 = [[1,0],[2,1],[1,2],[0,1],[.5,1.5],[1.5,1.5],[.5,.5],[1.5,.5]]
    c = getCircle(p1)
    print c

    if random.random() < 0.2:
        pnts = [(random.randrange(11), random.randrange(11)) for _ in range(500)]
    else:
        pnts = [(random.gauss(0, 1), random.gauss(0, 1)) for _ in range(500)]

    c = getCircle(pnts)
    print c


if __name__ == '__main__':
    _test()

