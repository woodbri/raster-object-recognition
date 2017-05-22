#!/bin/bash
if test  -z "$1" -o -z "$2" ; then
  echo "Usage: segment-one testnum doqq.tif"
  exit
fi
TESTNUM=$1
INFILE=$2

TMPDIR=/u/ror/buildings/tmp
SMOOTH=$TMPDIR/test$TESTNUM-smooth.tif
SMOOTHPOS=$TMPDIR/test$TESTNUM-smoothpos.tif
SEGS=$TMPDIR/test$TESTNUM-segs.tif
SHAPE=$TMPDIR/test$TESTNUM-segments.shp
TILESIZE=1025
HS=24
HR=36
MSIZE=128
RAM=102400
MPI="mpirun -np 4 --bind-to socket"

# code defaults to: -thres 0.001 -maxiter 4
# ror  defaults to: -thres 0.1 -maxiter 100

# OPTS="-thres 0.001 -maxiter 4"
OPTS="-thres 0.1 -maxiter 100"

date
CMD="$MPI otbcli_MeanShiftSmoothing -in $INFILE -fout $SMOOTH -foutpos $SMOOTHPOS -spatialr $HS -ranger $HR -ram $RAM $OPTS"
echo $CMD
time $CMD

date
CMD="otbcli_LSMSSegmentation -in $SMOOTH -inpos $SMOOTHPOS -out $SEGS -tmpdir $TMPDIR -spatialr $HS -ranger $HR -minsize $MSIZE -tilesizex $TILESIZE -tilesizey $TILESIZE"
echo $CMD
time $CMD

date
CMD="otbcli_LSMSVectorization -in $SMOOTH -inseg $SEGS -out $SHAPE -tilesizex $TILESIZE -tilesizey $TILESIZE"
echo $CMD
time $CMD

date
