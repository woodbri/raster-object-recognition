# CentOS Setup

```

USER=fluffybunny

# create a user account

adduser $USER
passwd $USER
usermod -G wheel $USER



# Installing docker:

# remove the base docker stuff if installed
sudo yum remove docker docker-common container-selinux docker-selinux docker-engine

# remove the base postgresql stuff if installed
sudo yum remove postgresql.x86_64 postgresql-contrib.x86_64 postgresql-libs.x86_64 postgresql-server.x86_64

sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum-config-manager --enable docker-ce-edge
sudo yum-config-manager --disable docker-ce-edge
sudo yum makecache fast
sudo yum install docker-ce
sudo systemctl start docker
sudo docker run hello-world

sudo yum install git-all.noarch

# installing postgresql 9.6

yum install https://download.postgresql.org/pub/repos/yum/9.6/redhat/rhel-7-x86_64/pgdg-redhat96-9.6-3.noarch.rpm

yum install postgresql96-server postgresql96-contrib postgresql96 postgresql96-libs

/usr/pgsql-9.6/bin/postgresql96-setup initdb

systemctl enable postgresql-9.6.service
systemctl start postgresql-9.6.service

vi /var/lib/pgsql/9.6/data/postgresql.conf
vi /var/lib/pgsql/9.6/data/pg_hba.conf

systemctl restart postgresql-9.6.service

# installing postgis

yum -y install epel-release
yum install postgis2_96 postgis2_96-client

# create a database

createdb -U postgres -h localhost buildings
psql -U postgres -h localhost buildings -c "create extension postgis"

# create a project directory, this matches what is defined in config.py

mkdir -p /u/ror/buildings
chown -R $USER.$USER /u


# login as regular user ($USER)

git clone https://github.com/woodbri/raster-object-recognition.git
cd raster-object-recognition
src/docker/docker-build

# change the database port to 5432
vi src/ror/config.py

# read the file, but this runs the docker instance as the current user.
src/docker/docker-run

cd raster-object-recognition/src

# this is the project config file
cat ror/config.py

./ror_cli.py                # see the various options
./ror_cli.py init-db        # create schemas and what not
./ror_cli.py census-fetch   # fetch and load the census data
./ror_cli.py naip-fetch -a 0603791400 	# fetch 8 doqqs for inglewood
./ror_cli.py naip-process -n 56         # process the raw naip files

# compute and display optimal parameters at this location
./ror_cli.py optimal-params -l 33.9062463,-118.3437712 -b

# run the segmentation for all of inglewood (run for 4 days)
./ror_cli.py segment -a 0603791400 -y 2014 -s 24 -r 36 -m 128 -d -R 102400 -j ingelwood1

# train and search have not been implemented yet
# don't have mapping tools integrated with this yet
# more work for the weary.

```

