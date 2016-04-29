
TIS-SysvolSync
====

TIS Sysvolsync is a solution for sync'ing the sysvol share on domain controlers
running Samba4 Active Directory. The sysvol share is a special share on an
Active Directory server where are stored netlogon scripts and GPO definitions.

The standard sysvol sync'ing technology on Microsoft is based on DFS-R which is
not currently implemented in Samba. This synchronisation method is not compatible
with DFS-R.

Tested on Debian 8 and CentOS 7. Packages available at the url below.

For more information : http://dev.tranquil.it/index.php/TIS-SysvolSync

Licensing
=========

Copyright: Tranquil It Systems http://www.tranquil-it-systems.fr/
License: GPL v3.0

The repository contains source code or binary (under the directory /lib/)
that come from other project and have their own licences.


Components of TIS-SysvolSync
============================

Python Environment
------------------

* Python 2.7.10
* Python 2.7 Requests
* Python 2.7 ldap
* Python 2.7 lxml

Syncthing
---------
Tested on syncthing >= 0.12.22


-- 
Hubert TOUVET
Tranquil IT Systems
02 40 97 57 57

