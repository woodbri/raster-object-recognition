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

### Docker

If you don't have Docker installed on your system, then go
[HERE](https://www.docker.com/) and find the downloads or instructions for
your system and install the Docker runtime.

There example scripts to build a Docker image and to run the Docker image in
``src/docker/``.

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

## Segmentation and Optimization of Parameters

A key to successful segmentation is picking parameters that are best suited to
the objects that you care about. There is no optimal parameters when you are
considering large scale areas. For example, think about the similarities and
differences in residential buildings, large commercial buildings, parking lots,
agricultural farmed areas at different times in the growing cycle. These are
might have some similar characteristics like they might be regularly shaped
objects, might have similar reflective characteristics, like gravel roof,
harvested dirt field plots, asphalt parking lots or roads.

The optimize-params option is based on the following papers and discussions
with the author Dr. Dongping Ming.

1. "Scale parameter selection by spatial statistics for GeOBIA: Using
mean-shift based multi-scale segmentation as an example", 2015, Dongping Ming, Jonathan Li, Junyi Wang, Min Zhang
2. "Modified average local variance for pixel-level scale selection of multiband remote sensing images and its scale effect on image classification accuracy", 2013, Dongping Ming, Jinyang Du, Xiyu Zhang, Tiantian Liu
3. "Modified ALV for selecting the optimal spatial resolution and its scale
effect on image classification accuracy", 2010, Dongping Ming, Jianyu Yang, Longxiang Li, Zhuoqin Song
4. "Modified Local Variance Based Method for Selecting the Optimal Spatial Resolution of Remote Sensing Image", 2010, Dongping Ming, Jiancheng Luo, Longxiang Li, Zhuoqin Song
5. "Semivariogram-Based Spatial Bandwidth Selection for Remote Sensing Image Segmentation With Mean-Shift Algorithm", 2012, Dongping Ming, Tianyu Ci, Hongyue Cai, Longxiang Li, Cheng Qiao, and Jinyang Du

From these papers, I decided to use the semivariogram approach to select the
optimal spatial bandwidth (Hs), then using that we create a LV (Local
Variance) image using Hs as the window size and fit a Gaussian curve to the
histogram of the LV image to select spectral bandwidth (Hr). And minimum
segment size (M) can be predicted from the spatial bandwidth.

This approach is not without some problems. For example:

1. the selection of Hs needs some work as there are still cases that I don't understand how to select the optimal parameter.
2. Using a Gaussian curve to fit to the histogram is not ideal, but it is fast and gives a reasonable approximation in most cases.

You can optionally have the code generate graphs of the curves that are being
evaluated to select the parameters, and I recommend that you use these to
evaluate the correctness of the parameters and to allow you to better make
manual adjustments to the results. While I have integrated the optimal parameter
selection into the segmentation as an option, I do not recommend using it for
production work.

As mentioned there is no optimal set of parameters that can be used globally,
so it is important to pick and area that is representative of the search area
when estimating the optimal parameters. You might need to breakdown the search
area into subareas that have similar spatial characteristics.

