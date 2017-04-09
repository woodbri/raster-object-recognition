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
from segment import segment
from workflow import workflow
from automate import automate
import rank, outline
import tools

if len(sys.argv) < 2:
  print "Usage: run-test2.py image"
  sys.exit(2)

files = automate( sys.argv[1], t=[20,50], s=[0.5], c=[0.3, 0.7],
                   do_stats=False, do_colorize=False, do_train=False,
                   do_classify=False, do_outline=True, do_lineup=True)
                   #do_classify=False, do_outline=False, do_lineup=False)

#files = segment( sys.argv[1], t=[20,50], tile=True )
#files = workflow( sys.argv[1], t=[20,50], tile=True )

print files

#all(map(os.path.exists, files))

#for f in files: os.remove( f )

