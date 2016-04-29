#!/bin/sh

set -ex
mkdir -p BUILD RPMS
rpmbuild -bb --buildroot $PWD/builddir -v --clean tis-sysvolsync.spec
cp RPMS/*/*.rpm .
