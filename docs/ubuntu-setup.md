# Ubuntu 16.04 Setup Proceedure for Raster Object Recognition

Assumes a new server. This was extracted from the Docker file so we 
setup a navtive Ubuntu 16.04 system.


```
USER=fluffybunny


adduser $USER
addgroup admin
adduser $USER admin
apt-get -qqy update && \
apt-get -qqy install software-properties-common && \
apt-get -qqy update && \
add-apt-repository -y ppa:ubuntugis/ubuntugis-experimental && \
apt-get -qqy update && \
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
    wget \
    git
apt-get -qqy install \
    postgresql-9.5 \
    postgresql-client-9.5 \
    postgresql-9.5-postgis-2.3 \
    postgresql-9.5-postgis-2.3-scripts
sed -i 's/^#listen_addresses/listen_addresses/' /etc/postgresql/9.5/main/postgresql.conf
sed -i 's/md5/trust/' /etc/postgresql/9.5/main/pg_hba.conf
service postgresql restart
createdb -U postgres -h localhost buildings
psql -U postgres -h localhost buildings -c "create extension postgis"
mkdir -p /u/ror/buildings
chown -R $USER.$USER /u
sed -i 's/python3/python2/' /usr/bin/rasterio
echo "try:" >> /etc/python2.7/sitecustomize.py && \
    echo "    import sys" >> /etc/python2.7/sitecustomize.py && \
    echo "    sys.path.append('/usr/lib/otb/python')" >> /etc/python2.7/sitecustomize.py && \
    echo "except:" >> /etc/python2.7/sitecustomize.py && \
    echo "    pass" >> /etc/python2.7/sitecustomize.py && \
    python -c 'from skimage import io'

```
