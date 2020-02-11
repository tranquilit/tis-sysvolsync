#!/bin/bash

set -ex
mkdir -p BUILD RPMS
VERSION=$(grep -o  -P "(?<=__version__ = ').*(?=')" ../sysvolsync.py)

wget -O syncthing.tar.gz https://github.com/syncthing/syncthing/releases/download/v$VERSION/syncthing-linux-amd64-v$VERSION.tar.gz
tar --strip-components=1 --wildcards -xvzf syncthing.tar.gz "syncthing*/syncthing"
cp syncthing ../bin/syncthing

rpmbuild -bb --buildroot $PWD/builddir -v --clean tis-sysvolsync.spec
cp RPMS/*/*.rpm .
