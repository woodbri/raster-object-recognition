#!/bin/sh

rm work-tiles/tile-0-0/*_*
rm work-tiles/tile-0-0/*jpg*
psql ma_buildings <<EOF
drop table seg_tileindex cascade;
drop table seg_polys cascade;
EOF
