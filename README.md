
TIS-SysvolSync
====

TIS Sysvolsync is a solution for sync'ing the sysvol share on domain controlers
running Samba4 Active Directory. The sysvol share is a special share on an
Active Directory server where are stored netlogon scripts and GPO definitions.

The standard sysvol sync'ing technology on Microsoft is based on DFS-R which is
not currently implemented in Samba. This synchronisation method is not compatible
with DFS-R.

Tested on Debian 11 and RHEL 8. Packages available at the url below.

For more information : https://samba.tranquil.it/doc/en/samba_advanced_methods/samba_tis_sysvolsync.html

Licensing
=========

Copyright: Tranquil It Systems https://www.tranquil.it
License: GPL v3.0

The repository contains source code or binary (under the directory /lib/)
that come from other project and have their own licences.


Components of TIS-SysvolSync
============================

Python Environment
------------------

* Python 3.6
* Python requests
* Python lxml

Syncthing
---------
Tested on syncthing v1.20.4
