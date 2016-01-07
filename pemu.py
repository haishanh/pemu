#!/usr/bin/env python
"""
qemu helper
haishanh
"""
import re
import os
import sys
import hashlib
import argparse
import subprocess
import ConfigParser


DEFAULT_VALUES = {
     'qemu'    : 'qemu-system-x86_64',
     'image'   : '',
     'memory'  : '2G',
     'cpu'     : 'host',
     'smp'     : 'cores=2,threads=1,sockets=1',
     'nic_nb'  : '1',
     'vnc_port': '',
     'extra'   : ''
}

ENV_OPTIONS = ['vm_nb']
GLOBAL_OPTIONS = ['base_vnc_port', 'qemu', 'image',
                  'memory', 'cpu', 'smp', 'nic_nb', 'extra']


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
    @param {string} s - a string to hash
    @param {number} id
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
            print('WARN: Invalid parameter: {0}'.format(opt))
        else:
            d[opt] = val
            if opt == 'vnc_port':
                vnc_port_set = True
    if not vnc_port_set and 'base_vnc_port' in confd['global']:
        d['vnc_port'] = ''

def cfg_init_env(cfg, confd):
    """
    populate confd['env']
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

    cfg = ConfigParser.ConfigParser()
    cfg.read(cf)

    assert 'global' in cfg.sections()
    confd = {}
    cfg_init_env(cfg, confd)
    cfg_init_global(cfg, confd)
    for sec in cfg.sections():
        cfg_init_individual(cfg, confd, sec)
    populate_conf(confd)
    return confd


def cfg_parse_env(cfg):
    ret = {}
    if 'env' not in cfg.sections():
        return ret

    for (opt, val) in cfg.items('env'):
        if opt in ENV_OPTIONS:
            ret[opt] = val
        else:
            print('WARN: {0} is not avaliable as a ' +
                    '<env> option - dropped'.format(opt))
    return ret


def cfg_parse_global(cfg):
    ret = {}
    if 'global' not in cfg.sections():
        return ret

    for (opt, val) in cfg.items('global'):
        if opt in GLOBAL_OPTIONS:
            ret[opt] = val
        else:
            print('WARN: {0} is not avaliable as a ' +
                  '<global> option - dropped'.format(opt))
    return ret

def cfg_parse_section(cfg, section):
    ret = {}
    ret.update(DEFAULT_VALUES)

    for (opt, val) in cfg.items(section):
        if opt in ret:
            ret[opt] = val
        else:
            print('WARN: {0} is not avaliable as a ' +
                  '<global> option - dropped'.format(opt))
    return ret


def cfg_parser2(cf):
    """
    parsing the config file
    @param {string} cf - the config file to parse
    """
    conf = {}
    used_ports = {}
    used_images = {}
    if not os.path.isfile(cf):
        print('ERROR: config file {0} not found'.format(cf))
        sys.exit(-1)

    cfg = ConfigParser.ConfigParser()
    cfg.read(cf)
    conf['env'] = cfg_parse_env(cfg)
    conf['global'] = cfg_parse_global(cfg)

    vm_nb = conf['env'].get('vm_nb', None)
    if vm_nb: vm_nb = int(vm_nb)

    # individual vm configuration
    i = 0
    j = 0 # store vm number
    base_port = conf['global'].get('base_vnc_port', '')
    for sec in cfg.sections():
        if sec in ['env', 'global']: continue
        if vm_nb:
            if j < vm_nb:
                j += 1
            else:
                print('WARN: vm_nb in <env> is {0}, vm <{1}> will not run\n'
                    .format(vm_nb, sec))
                break

        iconf = cfg_parse_section(cfg, sec)

        # resolve vnc_port and check
        port = iconf['vnc_port']
        if not port:
            if base_port:
                try:
                    port = str(int(base_port) + i)
                    i += 1
                except(e):
                    print('ERROR: base_vnc_port is not a number')
                    sys.exit(1)
            else:
                print('ERROR: vnc_port for {0} not defined'.format(sec))
                print('ERROR: base_vnc_port is also not avaliable in global confg')
                sys.exit(1)
        if port in used_ports:
            print('ERROR: vnc_port {0} already used by {1}'
                  .format(port, used_ports[port]))
            print(conf[used_ports[port]])
            sys.exit(1)

        used_ports[port] = sec
        iconf['vnc_port'] = port

        # image check
        # two running instances can't use a same image
        image = iconf['image']
        if not image:
            print('ERROR: image for {0} no specifyied'.format(sec))
            sys.exit(1)
        if image in used_images:
            print('ERROR: image {0} already used by {1}'
                  .format(image, used_images[image]))
            print(conf[used_images[image]])
            sys.exit(1)
        used_images[image] = sec

        nic_nb = int(iconf['nic_nb'])
        iconf['nic'] = []
        for i in range(nic_nb):
            nic = gen_virtio_dev(image, i)
            iconf['nic'].append(nic)

        conf[sec] = iconf

    return conf


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
                    ' ' + ' '.join(conf['nic']) + ' -vnc :' + \
                    conf['vnc_port'] + ' ' + conf['extra']
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
    cfgs = cfg_parser2(args['config_file'])
    for cfg in cfgs:
        if cfg in ('env', 'global'): continue
        vm = VM(cfg, cfgs[cfg])
        vm.run(args['dry_run'])

if __name__ == '__main__':
    args = parse_arguments()
    test(args)
