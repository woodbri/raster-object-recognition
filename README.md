# raster-object-recognition

## What is it?

Object recognition within rasters using machine learning. This is adapted
from aresearch project that evaluated the how to identify buildings in NAIP
DOQQ imagery. It uses various OpenSource tools and Python scripts to be a
work flow for this task. The whole process can be run from a Docker
container.

## The Work Flow

This is the basic work flow at a high level.

1. Download NAIP imagery for area of interest
2. Download some Census Tiger data and other misc GIS data
3. Build a training dataset of buildings
4. Segment the imagery for a training area
5. Build a training dataset based on 40% of training area
6. Run search in the 40% of training area
7. Review results of search
8. If results are not satisfactory, adjust parameters and goto 4.
9. Do a final check on remaining 20% of training area, Review and Loop is needed
10. Segment target search area
11. Run search in target search area
12. Review results
13. Post process the results

## Requirements

The processing pipeline system is built on Ubuntu 16.04 in a Docker container.
The Docker container is not required if you are already running Ubuntu 16.04+
or want to resolve the dependencies on your host system. See the file
*Dockerfile* for the list of packages to install.

### Use of host services

* Disk space through docker volume maps
* PostgreSQL database - The system makes extensive use of PostgreSQL database
* A Webserver - (optional) The current system as tools for visualizing data using mapserver and OpenLayers.

The database and mapserver could be configured to run inside the docker
container. There might be more information on this in the docs directory.

Lots of disk space. This depends on your area of interest, but the space is
needed for the NAIP imagery, segmentation polygons, database tables, etc.
The NAIP imagery for all of California was about 4TB for the raw data, We
compressed that down to about 1TB for a working set. In addition to that
we had about 1TB in PostgreSQL tables. Regardless, plan for this and monitor
your usage.

## Directory Structure

```
project/
    README.md
    Dockerfile
    bin/                - all executables and scripts get copied here
    data/
        buildings/
            osm/        - (optional) buildings extracted from OSM
            training/   - (optional) buildings dataset for training
            results/    - search results after post processing
        census/         - Census TIGER data that is useful
            counties/
            cousub/
            roads/
        dbdump/         - place to store database dumps for backups
        naip/           - NAIP imagery downloaded and processed
        segments/       - output of the image segmentation processes
    docs/               - project documentation
    maps/               - (optional) visualization using mapserver
        cgi-bin/
        html/
    src/
        osm-buildings/  - C++ code to extract build polygons from OSM
        naip-fetch/     - scripts assist in fetching NAIP imagery
        naip-process/   - scripts to post process the raw NAIP imagery
        workflow/       - scripts that perform the various steps in the workflow
```


