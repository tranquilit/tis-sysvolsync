#!/usr/bin/python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
#    This file is part of tis-sysvolsync
#    Copyright (C) 2013  Tranquil IT Systems http://www.tranquil.it
#
#    tis-sysvolsync is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    tis-sysvolsync is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with tis-sysvolsync.  If not, see <http://www.gnu.org/licenses/>.
#
# ---------------------------------------------------------------------
#
# Sample script which updates acl of samba4 sysvol upon completion with
#   syncthing
#------------------------------------------------
"""
Daemon Script which updates acl of samba4 sysvol upon completion with syncthing

Usage : %s [options] <action>

<action> is one of
  configure : initialize syncthing with ADS topology
  watch : connect to local syncthing and wait for sysvol sync completion and launch "samba-tool ntacl sysvolreset"
  info : get a json of local ID, ports for remote AD configuration
  status : get a json of sysvol sync status
  add-remote : connect to remote host to add sysvol share with localhost, add local share too.
                takes 3 arguments: remote ID, name and address.
                example:  add-remote AAAA-BBBB-CCC srvads2.test.lan tcp://srvads2.test.lan:22001
"""

__version__ = '0.2.0'

import sys
import os
import requests
import time
import json
import subprocess
import logging
from lxml import etree
import logging
from optparse import OptionParser
import ldif
from  StringIO import StringIO
import re
from collections import MappingView
import shutil

logger = logging.getLogger('sysvol-fixacl')

def samba_domain_info(ads_ip = '127.0.0.1'):
    """Return a dict of domain infos given IP of domain controller"""
    rawinfos = subprocess.check_output('samba-tool domain info %s' % ads_ip,shell=True)
    """
    Forest           : touvet.lan
    Domain           : touvet.lan
    Netbios domain   : TOUVET
    DC name          : srvads1.touvet.lan
    DC netbios name  : SRVADS1
    Server site      : Default-First-Site-Name
    Client site      : Default-First-Site-Name
    """
    result = {}
    for l in rawinfos.splitlines():
        if ':' in l:
            key,value = l.split(':',2)
            result[key.strip()] = value.strip()
    return result


class SyncThing(object):

    def __init__(self,config_filename = r'/opt/tis-sysvolsync/data/config.xml'):
        self.config_filename = config_filename
        self.read_syncthing_config()

        # need apikey for that...
        self.id = self.get_syncthing_id()

        if self.apikey == 'gkJ9e76WoQVLAKmPjXLlyrydNX3Hctxy':
            self.generate_apikey()


        logger.info('ID : %s' % self.id)
        logger.info('api port : %s' % self.apiport)
        logger.info('api key : %s' % self.apikey)
        logger.info('data port : %s' % self.dataport)

    def generate_apikey(self):
        # todo
        oldkey = self.apikey[:]
        self.apikey = os.urandom(32).encode("base64")[:-2]
        xmldata = open(self.config_filename).read()
        config = etree.parse(StringIO(xmldata))
        config.xpath('/configuration/gui/apikey')[0].text = self.apikey
        config.write(self.config_filename,encoding='utf8',pretty_print=True)
        current_key = self.syncthing_rest_get('system/config',apikey='')['gui']['apiKey']
        return self.syncthing_rest_post('system/restart',apikey=current_key)


    def read_syncthing_config(self):
        xmldata = open(self.config_filename).read()
        config = etree.parse(StringIO(xmldata))
        self.apikey = config.xpath('/configuration/gui/apikey')[0].text
        self.apiport = int(config.xpath('/configuration/gui/address')[0].text.split(':')[-1])
        self.dataport = int(config.xpath('/configuration/options/listenAddress')[0].text.split(':')[-1])

    def get_syncthing_config(self):
        return dict(
            id = self.id,
            apikey = self.apikey,
            apiport = self.apiport,
            dataport = self.dataport,
            )

    def syncthing_rest_get(self,path,apikey=None):
        try:
            if apikey is None:
                apikey = self.apikey
            data = requests.get('http://127.0.0.1:%s/rest/%s' % (self.apiport,path), headers={'X-API-Key':apikey}, proxies={'http':None,'https':None})
            try:
                return json.loads(data.content or 'none')
            except:
                logger.critical('Error in data : %s for path %s' % (data.content,path))
                raise
        except requests.HTTPError as e:
            print('Syncthing service can not be contacted. Check if it is running\n  ie.  "systemctl status tis-sysvolsync"')
            logger.critical("%s"%e)
            raise


    def syncthing_rest_post(self,path,data='',apikey=None):
        try:
            if apikey is None:
                apikey = self.apikey
            result = requests.post('http://127.0.0.1:%s/rest/%s' % (self.apiport,path), data=json.dumps(data), headers={'X-API-Key':apikey}, proxies={'http':None,'https':None})
            try:
                return json.loads(result.content or 'none')
            except:
                logger.critical('Error in data : %s for path %s' % (result.content,path))
                raise
        except requests.HTTPError as e:
            print('Syncthing service can not be contacted. Check if it is running\n  ie.  "systemctl status tis-sysvolsync"')
            logger.critical("%s"%e)
            raise

    def get_syncthing_id(self):
        """Return local syncthing device ID"""
        return self.syncthing_rest_get('system/status')['myID']

    def get_folder_status(self,folder='sysvol'):
        return self.syncthing_rest_get('db/status?folder=%s' % folder)

    def get_connections(self):
        return self.syncthing_rest_get('system/connections')

    def wait_completion(self,folder='sysvol'):
        """Connect to local syncthing and wait fr the completion of sysvol directoyr, then fix ACL on sysvol"""
        last_event = 0
        myid = self.get_syncthing_id()
        while True:
            try:
                logger.debug('Get events... (blocking until event id > %i)' % last_event)
                events = self.syncthing_rest_get('events?since=%i'%last_event)
                logger.debug('%i events to analyse' % (len(events),))
                for event in reversed(events):
                    last_event = max([last_event,event['id']])
                    if event['type'] == 'FolderCompletion' \
                            and event['data']['folder'] == folder \
                            and event['data']['completion'] >= 100 \
                            and event['data']['device'] != myid :
                        logger.info("Fix ACL on %s..." % folder)
                        try:
                            logger.info(subprocess.check_output('samba-tool ntacl sysvolreset',shell=True))
                            break
                        except Exception as e:
                            logger.critical("sysvolreset error: %s" % e)
                            break

            except Exception as e:
                logger.debug('%s ... sleeping' % e)
                time.sleep(2)

    def add_sysvol(self,folderid='sysvol',localpath='/var/lib/samba/sysvol',remote_devices=[]):
        """Add the sync of a local drirectory with remote hosts"""
        logger.debug('Adding folder id %s shared with devices %s' % (folderid,remote_devices))
        if isinstance(remote_devices,str):
            remote_devices = [ remote_devices ]
        localconf = self.syncthing_rest_get('system/config')
        folders = localconf['folders']
        sysvol = [ f for f in folders if f['id'] == folderid or f['path'] == localpath]
        updated = False
        if sysvol:
            logger.debug('Folder %s already exists, checking sharing'%folderid)
            sysvol = sysvol[0]
            for device in remote_devices:
                if not  {'deviceID':device} in sysvol['devices']:
                    logger.debug('Adding device %s to folder %s'%(device,folderid))
                    sysvol['devices'].append({'deviceID':device})
                    updated = True

        else:
            folders.append( dict(
                id = folderid,
                path = localpath,
                devices = [ {'deviceID':dev} for dev in  remote_devices],
                readOnly = False,
                ignorePerms = True,
                autoNormalize= True,
                rescanIntervalS = 60,
                ))
            logger.debug('Adding folder %s with devices %s' % (folderid,remote_devices))
            updated = True
        if updated:
            logger.debug('Push config to syncthing')
            self.syncthing_rest_post('system/config',data=localconf)

    def add_remote_server(self,id,name,address):
        """Add a remote host in the syncthing configuration"""
        localconf = self.syncthing_rest_get('system/config')
        devices = localconf['devices']
        device = [d for d in devices if d['deviceID'] == id]
        if device:
            logger.debug('remote device %s already exists, checking config...'%id)
            device = device[0]
            if not address in device['addresses'] or device['name'] != name:
                device['name'] = name
                if not address in device['addresses']:
                    logger.debug('remote device %s : updateing address to %s' % (id, address))
                    device['addresses'].append(address)
                logger.debug('Post syncthing config')
                self.syncthing_rest_post('system/config',data=localconf)
                return True
            else:
                return False
        else:
            logger.debug('Adding remote device %s with address %s'%(id,address))
            devices.append( dict(
                deviceID = id,
                name = name,
                addresses = [ address ],
                ))
            logger.debug('Post syncthing config')
            self.syncthing_rest_post('system/config',data=localconf)
            return True

    def check_config_loaded(self):
        """Check if syncthing stored config is same as running one, if not restart syncthing"""
        logger.debug('Check if syncthing config should be reloaded...')
        config_loaded = self.syncthing_rest_get('system/config/insync')['configInSync']
        if not config_loaded:
            logger.info('Restart syncthing')
            self.syncthing_rest_post('system/restart','')
            return True
        else:
            logger.debug('Syncthing config unchanged')
            return False


    def add_mutual_sysvol_sync(self,local_hostname,remote_hostname,folderid='sysvol',localpath='/var/lib/samba/sysvol'):
        """Connect with SSH to remote ADS to add localhost sysvol and get syncthing ID and config"""
        print('Connecting to %s using SSH to add myself as remote devide, add sysvol sync and get syncthing configuration...'% remote_hostname)
        remote_jsonconfig = subprocess.check_output('ssh %s python /opt/tis-sysvolsync/sysvolsync.py -ldebug -f /var/log/sysvolbind.log add-remote %s %s tcp://%s:%s' % (
                remote_hostname,self.id,local_hostname,local_hostname,self.dataport),shell=True)
        remote_syncthing_config = json.loads(remote_jsonconfig)
        print("Adding remote server : %s with key '%s'" % (remote_hostname,remote_syncthing_config['id']))
        self.add_remote_server(
            remote_syncthing_config['id'],
            address='tcp://%s:%s'%(remote_hostname,remote_syncthing_config['dataport']),
            name=remote_hostname)
        self.add_sysvol(folderid=folderid,localpath=localpath,remote_devices = [remote_syncthing_config['id']])
        self.check_config_loaded()
        return json.loads(remote_jsonconfig)

def setloglevel(loglevel):
    """set loglevel as string"""
    if loglevel in ('debug','warning','info','error','critical'):
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        logger.setLevel(numeric_level)

def get_remote_syncthing_config(host):
    """Connect with SSH to remote ADS to get syncthing ID"""
    print('Connecting to %s using SSH to get remote syncthing sync configuration...'% host)
    jsonconfig = subprocess.check_output('ssh %s python /opt/tis-sysvolsync/sysvolsync.py info' % host,shell=True)
    return json.loads(jsonconfig)


def extract_ntds_server_name(dn):
    """Extract a server net bios name from a DN in AD ntds object values"""
    # CN=ede7ba75-cd25-429d-afc4-ad8ba67aafc6,CN=NTDS Settings,CN=SRVADS,CN=Servers,CN=aDefault-First-Site-Name,CN=Sites,CN=Configuration,DC=tranquilit,DC=local
    DN_RE = r"CN=NTDS Settings,CN=(.*),CN=Servers"
    server_cn = re.findall(DN_RE,dn)
    return server_cn and server_cn[0] or ''

def get_drs_connections(dn='dc=touvet,dc=lan'):
    if os.path.isdir('/usr/lib64/samba/ldb'):
        ldb_modules = 'LDB_MODULES_PATH=/usr/lib64/samba/ldb/ '
    else:
        ldb_modules = ''

    ntds = ldif.ParseLDIF(StringIO(subprocess.check_output('%sldbsearch -b %s -H /var/lib/samba/private/sam.ldb --cross-ncs  "(objectClass=ntdsconnection)" dn fromServer cn name distinguishedName' %
        (ldb_modules,dn) ,shell=True)))
    result = []
    for (connection_dn,connection) in ntds:
        from_server = extract_ntds_server_name(connection['fromServer'][0])
        to_server = extract_ntds_server_name(connection_dn)
        result.append((from_server,to_server))
    return result


def main():
    parser=OptionParser(usage=__doc__)
    parser.add_option("-f","--logfilename", dest="logfilename", default='', help="Log filename (default: %default)")
    parser.add_option("-l","--loglevel", dest="loglevel", default=None, type='choice',  choices=['debug','warning','info','error','critical'], metavar='LOGLEVEL',help="Loglevel (default: info)")
    parser.add_option("-V","--version", dest="getversion", default=False, action = 'store_true', help="Get version")

    (options,args) = parser.parse_args()

    if options.getversion:
        print __version__,
        sys.exit(0)

    if not options.logfilename:
        hdlr = logging.StreamHandler(sys.stderr)
        hdlr.setFormatter(logging.Formatter(u'%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr)
    else:
        hdlr = logging.FileHandler(options.logfilename )
        hdlr.setFormatter(logging.Formatter(u'%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(hdlr)

    if options.loglevel:
        setloglevel(options.loglevel)
    else:
        setloglevel('info')

    syncthing = SyncThing()

    action = 'watch'
    if args:
        action = args[0]

    if action == 'info':
        print json.dumps(syncthing.get_syncthing_config(),indent=True)

    if action == 'add-remote':
        logger.debug(args)
        if len(args)<4:
            logger.critical('add-remote takes 3 arguments: remote ID, name and address.\n example: %s add-remote AAAA-BBBB-CCC srvads2.test.lan tcp://srvads2.test.lan:22001')
            exit(1)
        logger.debug("Adding ID '%s' with name %s at address %s" % (args[1],args[2],args[3]))
        syncthing.add_remote_server(args[1],args[2],args[3])
        syncthing.check_config_loaded()
        syncthing.add_sysvol(remote_devices = [args[1],])
        syncthing.check_config_loaded()
        print json.dumps(syncthing.get_syncthing_config(),indent=True)

    if action == 'status':
        print json.dumps(dict(
            sysvol = syncthing.get_folder_status('sysvol'),
            connections = syncthing.get_connections(),
            ),indent=True)

    if action == 'configure':
        # get replication topology from local AD using ldbsearch and add mutual sysvol sync
        syncthing.check_config_loaded()
        try:
            domain_info = samba_domain_info()
            print domain_info
        except Exception as e:
            print('Local domain information can not be retrieved. Is samba started and configfured ?')
            logger.critical('%s' % e)
            exit(1)

        local_dc = domain_info['DC name']

        dn = ','.join(['dc=%s' % m for m in domain_info['Domain'].split('.')])
        print('Get DRS connections informations from local LDB AD database...')
        connections = get_drs_connections(dn)
        for from_host,to_host in connections:
            # comparison with uppercase short name;..
            if to_host == domain_info['DC netbios name']:
                print('Configuring sync from %s to %s' % (from_host,to_host))
                remote_info = samba_domain_info(from_host)
                print('Remote host infos : %s' % remote_info)
                remote_dc = remote_info['DC name']
                # will ask for a password...
                syncthing.add_mutual_sysvol_sync(local_dc,remote_dc)
        print('Reload syncthing process')
        syncthing.check_config_loaded()

    if action == 'watch':
        syncthing.check_config_loaded()
        syncthing.wait_completion()


if __name__ == '__main__':
    main()
