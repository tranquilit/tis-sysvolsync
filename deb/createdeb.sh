#!/usr/bin/env bash
VERSION=$(python ../sysvolsync.py -V)

rm -f *.deb
rm -Rf builddir
mkdir builddir
mkdir builddir/DEBIAN
cp ./control ./builddir/DEBIAN
cp ./postinst ./builddir/DEBIAN
chmod 755 ./builddir/DEBIAN/postinst

sed "s/VERSION/$VERSION/" -i ./builddir/DEBIAN/control

mkdir -p ./builddir/etc/tis-sysvolsync
mkdir -p ./builddir/opt/tis-sysvolsync/bin
mkdir -p ./builddir/opt/tis-sysvolsync/data
mkdir -p ./builddir/opt/tis-sysvolsync/templates
mkdir -p ./builddir/etc/logrotate.d

# systemd
mkdir -p ./builddir/lib/systemd/system

cp ../sysvolsync.py  ./builddir/opt/tis-sysvolsync/
chmod 755 ./builddir/opt/tis-sysvolsync/*.py

cp ../templates/config.xml.template ./builddir/opt/tis-sysvolsync/templates

cp ../bin/syncthing  ./builddir/opt/tis-sysvolsync/bin/
chmod 755 ./builddir/opt/tis-sysvolsync/bin/syncthing

cp ../files/tis-sysvolacl.service ./builddir/lib/systemd/system/
cp ../files/tis-sysvolsync.service ./builddir/lib/systemd/system/

cp ../files/logrotate.sysvolsync ./builddir/etc/logrotate.d/sysvolsync

dpkg-deb --build builddir tis-sysvolsync-${VERSION}.deb

echo "== Copie du .deb sur le serveur tisdeb =="
rsync -azP *.deb root@srvinstallation.tranquil.it:/var/www/srvinstallation/tisdeb/binary

echo "== Scan du répertoire =="
ssh root@srvinstallation.tranquil.it /var/www/srvinstallation/tisdeb/updateRepo.sh
