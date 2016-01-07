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
GLOBAL_OPTIONS = ['base_vnc_port', 'qemu',
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


def cfg_parse_env(cfg):
    """
    parse env section
    ---
    [env]
    vm_nb = 10
    """
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
    """
    parse global section
    ---
    [global]
    base_vnc_port = 40
    """
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

def cfg_parse_section(cfg, section, glb):
    ret = {}

    for (opt, val) in cfg.items(section):
        if opt in DEFAULT_VALUES:
            ret[opt] = val
        else:
            print('WARN: {0} is not avaliable as a ' +
                  'vm config option - dropped'.format(opt))

    for key in DEFAULT_VALUES:
        if key in glb and key not in ret:
            ret[key] = glb[key]
        else:
            if key not in ret:
                ret[key] = DEFAULT_VALUES[key]

    return ret


def cfg_parser(cf):
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
    i = 0 # for vnc port increment
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

        iconf = cfg_parse_section(cfg, sec, glb=conf['global'])

        # resolve vnc_port and check
        port = iconf['vnc_port']
        if not port:
            if base_port:
                try:
                    port = str(int(base_port) + i)
                    i += 1
                except:
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
            qemu_cmd += ' -enable-kvm'
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
    parser.add_argument('-d', '--dry-run', dest='dry_run',
                        action='store_true', default = False, help='Dry run')
    parser.add_argument('-f', '--config-file', dest='config_file',
                        default='vm.ini',
                        help='Specify config file(use ./vm.ini by  defualt)')
    return vars(parser.parse_args())

def main(args):
    cfgs = cfg_parser(args['config_file'])
    for cfg in cfgs:
        if cfg in ('env', 'global'): continue
        vm = VM(cfg, cfgs[cfg])
        vm.run(args['dry_run'])

if __name__ == '__main__':
    args = parse_arguments()
    main(args)
