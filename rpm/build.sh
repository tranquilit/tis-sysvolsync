#!/bin/sh

set -ex
mkdir -p BUILD RPMS

wget -O syncthing.tar.gz https://github.com/syncthing/syncthing/releases/download/v0.12.22/syncthing-linux-arm64-v0.12.22.tar.gz 
tar --strip-components=1 --wildcards -xvzf syncthing.tar.gz "syncthing*/syncthing" 
cp syncthing ../bin/syncthing

rpmbuild -bb --buildroot $PWD/builddir -v --clean tis-sysvolsync.spec
cp RPMS/*/*.rpm .
