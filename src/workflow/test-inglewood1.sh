#!/bin/sh

# clean out old segmentation files
# ie: remove everything except the source tiles
rm inglewood1/tile-*/tile-??.{vrt,tif}_* inglewood1/tile-*/*jpg*

./segment-dir.py -m 5b -t 50 -s 0.3 -c 0.3  inglewood1/

./load-seg-data.py -p test1 -m 5b inglewood1 inglewood1/

# -z 150 - only use buildings larger than 90 sq-m for training

./prep-relevance.py -b inglewood1_test1_5b_50_03_03 -j inglewood1 -p test1 -m 5b -t 50 -s 0.3 -c 0.3 -z 150

# The following take 50% of the segments and use them for training
# Then takes the remainder and uses them for prediction
# Then print out the results of the test
#
# -r num is the cutoff in pctoverlap that is used when training
# if the pctoverlap is smaller than -r num it will not be trained
# as part of the class

echo '--------- -r 0.5 ------------'
./train-segments.py -j inglewood1 -p test1 -m 5b -r 0.5 -b inglewood1_test1_5b_50_03_03 -x inglewood1-train.pkl.gz

echo '--------- -r 0.1 ------------'
./train-segments.py -j inglewood1 -p test1 -m 5b -r 0.1 -b inglewood1_test1_5b_50_03_03 -x inglewood1-train.pkl.gz

echo '--------- -r 0.2 ------------'
./train-segments.py -j inglewood1 -p test1 -m 5b -r 0.2 -b inglewood1_test1_5b_50_03_03 -x inglewood1-train.pkl.gz

echo '--------- -r 0.08 ------------'
./train-segments.py -j inglewood1 -p test1 -m 5b -r 0.08 -b inglewood1_test1_5b_50_03_03 -x inglewood1-train.pkl.gz
