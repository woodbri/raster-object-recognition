# Run Orfeo Toolbox in a container [option to execute otb cli and gui commands]
#
# docker run -i -t \
#        -v $HOME/Data:/home/data  \  <- mounts data directory to container
#        toddstavish/orfeo_toolbox \
#        otb_cli_gui executable       <- otb command and parameters [defaults to shell]
#
# GUI Dependencies: Linux -> -v /tmp/.X11-unix:/tmp/.X11-unix and -e DISPLAY=unix$DISPLAY
#                   OSX -> XQuartz and
#                          socat TCP-LISTEN:6000,reuseaddr,fork UNIX-CLIENT:\"$DISPLAY\" and
#                          -e DISPLAY=192.168.99.1:0 <- this the default virtualbox ip address
#
#          monteverdi2 mesa-utils xserver-xorg-video-all \
#

FROM ubuntu:16.04
MAINTAINER Stephen Woodbridge <woodbri@imaptools.com>

RUN apt-get -qqy update &&\
        apt-get -qqy install software-properties-common &&\
        apt-get -qqy update &&\
        add-apt-repository ppa:ubuntugis/ppa &&\
        apt-get -qqy update &&\
        apt-get -qqy install \
          gdal-bin \
          imagemagick \
          libotb \
          libterm-readline-perl-perl \
          locales-all \
          monteverdi \
          otb-bin \
          otb-bin-qt \
          python-setuptools \
          python-pkg-resources \
          python-gdal \
          python-matplotlib \
          python-matplotlib-data \
          python-otb \
          python-rasterio \
          python-scipy \
          python-sciscipy \
          python-scitools \
          python-simplejson \
          python-skimage \
          python-sklearn \
          python-psycopg2 \
          python-numpy \
          rasterio \
          sudo \
          vim \
          && \
        apt-get clean && \
        rm -rf /var/lib/apt/lists/* && \
        sed -i 's/python3/python2/' /usr/bin/rasterio && \
        echo "try:" >> /etc/python2.7/sitecustomize.py && \
        echo "    import sys" >> /etc/python2.7/sitecustomize.py && \
        echo "    sys.path.append('/usr/lib/otb/python')" >> /etc/python2.7/sitecustomize.py && \
        echo "except:" >> /etc/python2.7/sitecustomize.py && \
        echo "    pass" >> /etc/python2.7/sitecustomize.py && \
        python -c 'from skimage import io'


ENTRYPOINT
CMD ["/bin/bash"]
