#!/usr/bin/env python
"""
qemu helper
haishanh
"""
import re
import os
import sys
import hashlib
import logging
import argparse
import subprocess
import ConfigParser


QEMU_GLOBAL_OPTIONS = ['qemu', 'image', 'memory', 'cpu', 'nic_nb', 'base_vnc_port']

QEMU_DEFAULT_CONFG = { 'qemu'  : 'qemu-system-x86_64',
                       'image'   : '/home/haishanh/images/arch-copy.qcow2',
                       'memory': '2G',
                       'cpu'   : 'host',
                       'smp'   : 'cores=2,threads=1,sockets=1',
                       'nic_nb': '1',
                       'vnc_port': '10' }

LOG = logging.getLogger('pemu')

def sh(c, check=False):
    p = subprocess.Popen(c, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    print(p.pid)
    if check:
        p.wait()
        return p.stdout


def mac_hash(s):
    """
    return a valid virtual MAC addr
    """
    m = hashlib.md5()
    m.update(s)
    m = m.hexdigest()[0:8]
    return "52:54:%s%s:%s%s:%s%s:%s%s" % tuple(m)


def gen_virtio_dev(s, id):
    """
    generate `-netdev` and `-dev` args for qemu
    """
    mac = mac_hash(s + str(id))
    netdev = '-netdev tap,id=hostnet' + str(id) + \
             ',script=no,downscript=no,vhost=on'
    dev = '-device virtio-net-pci,netdev=hostnet'+ \
          str(id) +',mac=' + mac
    return netdev + ' ' + dev


def cfg_get(callback, option, section='global'):
    """
    defensive `get` method of ConfigParser class
    callback should be one of [ 'get', 'getboolean', 'getfloat', 'getint' ]
    Usage:
        cfg = ConfigParser.ConfigParser()
        cfg.read(cf)
        x = cfg_get(cfg.getint, 'vm_nb', 'global')
    """
    if callback.im_self.has_option(section, option):
        return callback(section, option)
    else:
        return None

def cfg_init_global(cfg, confd):
    """
    populate confd['global']
    cfg is a ConfigParser.ConfigParser() instance
    """
    d = {}
    # changes made to `d` affect `confd` as well
    confd['global'] = d
    # update `d` with *default* qemu options
    # d.update(QEMU_OPTIONS)
    # overwrite
    for option in QEMU_GLOBAL_OPTIONS:
        x = cfg_get(cfg.get, option, 'global')
        if x:
            d[option] = x


def cfg_init_individual(cfg, confd, vm):
    """
    populate confd[vm]
    cfg is a ConfigParser.ConfigParser() instance
    """
    if vm in ('env', 'global'):
        return
    vnc_port_set = False
    d = {}
    confd[vm] = d
    for key in QEMU_DEFAULT_CONFG.keys():
        d[key] = QEMU_DEFAULT_CONFG[key]
    d.update(confd['global'])
    for (opt, val) in cfg.items(vm):
        if opt not in QEMU_DEFAULT_CONFG.keys():
            LOG.warning('Invalid parameter: {0}'.format(opt))
        else:
            d[opt] = val
            if opt == 'vnc_port':
                vnc_port_set = True
    if not vnc_port_set and 'base_vnc_port' in confd['global']:
        d['vnc_port'] = ''

def cfg_init_env(cfg, confd):
    """
    polulate confd['env']
    cfg is a ConfigParser.ConfigParser() instance
    """
    d = {}
    confd['env'] = d
    d['vm_nb'] = '1'
    # overwrite
    for option in d.keys():
        x = cfg_get(cfg.get, option, 'env')
        if x: d[option] = x


def populate_conf(confd):
    """
    populate configurations
    """
    # TODO consider do validation also in this function
    if 'base_vnc_port' in confd['global']:
        base_vnc_port = int(confd['global']['base_vnc_port'])
    else:
        base_vnc_port = 10
    vnc_port = base_vnc_port
    # it's not good
    images_used = []
    for sec in confd:
        if sec in ('env', 'global'): continue
        conf = confd[sec]
        nic_nb = int(conf['nic_nb'])
        if conf['image'] in images_used:
            print('CRITICAL: Same image used for multiple VMs')
            sys.exit(1)
        images_used.append(conf['image'])
        conf['nic'] = []
        for i in range(nic_nb):
            # netdev = 'tap,id=hostnet' + str(i) + \
            #          ',script=no,downscript=no,vhost=on'
            # device = 'virtio-net-pci,netdev=hostnet' + str(i) + \
            #          ',mac=' + mac_hash(conf['img'], i)
            # conf['nic'].append((netdev, device))
            nic = gen_virtio_dev(conf['image'], i)
            conf['nic'].append(nic)
        if not conf['vnc_port']:
            conf['vnc_port'] = str(vnc_port)
            vnc_port += 1

def cfg_parser(cf):
    """
    parsing the config file
    """
    if not os.path.isfile(cf):
        print('ERROR: config file {0} not found'.format(cf))
        sys.exit(-1)
    # TODO add defence here
    cfg = ConfigParser.ConfigParser()
    cfg.read(cf)
    # TODO
    assert 'global' in cfg.sections()
    confd = {}
    cfg_init_env(cfg, confd)
    cfg_init_global(cfg, confd)
    for sec in cfg.sections():
        cfg_init_individual(cfg, confd, sec)
    populate_conf(confd)
    return confd


class QemuArgs(object):
    def __init__(self, name, conf):
        self.name = name
        if not 'enable-kvm' in conf:
            conf['enable-kvm'] = True
        if not 'nographic' in conf:
            conf['nographic'] = True
        self.conf = conf


    def gen_args(self):
        spre = re.compile(r'\s(?=--?[a-z][\w]*)')
        conf = self.conf
        qemu_cmd = conf['qemu']
        if conf['enable-kvm']:
            qemu_cmd += ' --enable-kvm'
        if conf['nographic']:
            qemu_cmd += ' -nographic'
        qemu_cmd += ' -m ' + conf['memory'] + ' -cpu ' + conf['cpu'] + \
                    ' -smp ' + conf['smp'] + ' -hda ' +  conf['image'] + \
                    ' ' + ' '.join(conf['nic']) + ' -vnc :' + conf['vnc_port']
        _ = spre.split(qemu_cmd)
        beautiful_cmd = ' \\\n'.join(_)
        return qemu_cmd, beautiful_cmd

class VM(object):
    """
    modelling a QEMU/KVM virtual machine
    """
    def __init__(self, name, conf):
        """
        name is a string
        conf is the config for this specific VM
        """
        self.name = name
        self.conf = conf

    def run(self, dry_run):
        """
        bring the VM up
        """
        qemu_args = QemuArgs(self.name, self.conf)
        qemu_cmd, beautiful_cmd = qemu_args.gen_args();
        # conf = self.conf
        # qemu_cmd = conf['qemu'] + ' --enable-kvm' + ' -nographic' + \
        #            ' -m ' + conf['memory'] + ' -cpu ' + conf['cpu'] + \
        #            ' -smp ' + conf['smp'] + ' -hda ' +  conf['image'] + \
        #            ' ' + ' '.join(conf['nic']) + ' -vnc :' + conf['vnc_port']
        if dry_run:
            print(beautiful_cmd)
            print('\n')
        else:
            sh(qemu_cmd)

def parse_arguments():
    """
    Parse sys.argv, return as a dict
    """
    parser = argparse.ArgumentParser(description="Qemu wrapper")
    parser.add_argument('-d', '--dry-run', dest='dry_run', action='store_true', default = False, help='Dry run')
    parser.add_argument('-f', '--config-file', dest='config_file', default='vm.ini', help='Specify config file')
    return vars(parser.parse_args())

def test(args):
    cfgs = cfg_parser(args['config_file'])
    for cfg in cfgs:
        if cfg in ('env', 'global'): continue
        vm = VM(cfg, cfgs[cfg])
        vm.run(args['dry_run'])

if __name__ == '__main__':
    args = parse_arguments()
    test(args)
