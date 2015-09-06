#!/usr/bin/env python
"""
qemu helper
haishanh
"""
import hashlib
import logging
import subprocess
import ConfigParser

dry_run = True
QEMU_OPTIONS = { 'qemu'  : 'qemu-system-x86_64',
                 'img'   : '/home/haishanh/images/arch-copy.qcow2',
                 'memory': '2G',
                 'cpu'   : 'host',
                 'smp'   : 'cores=2,threads=1,sockets=1', 
                 'nic_nb': '1' } 

def sh(c, check=False):
    p = subprocess.Popen(c, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    print(p.pid)
    if check:
        return p.wait()

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


def start_vm():
    """
    start a VM
    """
    img = '/home/haishanh/images/arch-copy.qcow2'
    base_vnc_port = 35
    smp = 'cores=2,threads=1,sockets=1'
    virtio_dev = gen_virtio_dev(img, 0)
    # here comes the command
    cmd = 'numactl --cpunodebind=0 --membind=0'
    cmd += ' qemu-system-x86_64 --enable-kvm -nographic -m 3G'
    cmd += ' -cpu host'
    cmd += ' -smp ' + smp
    cmd += ' -hda ' + img
    cmd += ' ' + virtio_dev
    cmd += ' -vnc :' + str(base_vnc_port)
    print(cmd)
    sh(cmd)



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
    d.update(QEMU_OPTIONS)
    # overwrite
    for option in d.keys():
        x = cfg_get(cfg.get, option, 'global')
        if x: d[option] = x

def cfg_init_individual(cfg, confd, vm):
    """
    populate confd[vm]
    cfg is a ConfigParser.ConfigParser() instance
    """
    if vm in ('env', 'global'):
        return
    d = {}
    confd[vm] = d
    d.update(confd['global'])
    for (opt, val) in cfg.items(vm):
        if opt not in QEMU_OPTIONS:
            logging.warning('Invalid parameter: {0}'.format(opt))
        else:
            d[opt] = val 

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
    base_vnc_port = 40
    vnc_port = base_vnc_port
    for sec in confd:
        if sec in ('env', 'global'): continue
        conf = confd[sec]
        nic_nb = int(conf['nic_nb'])
        conf['nic'] = []
        for i in range(nic_nb):
            # netdev = 'tap,id=hostnet' + str(i) + \
            #          ',script=no,downscript=no,vhost=on'
            # device = 'virtio-net-pci,netdev=hostnet' + str(i) + \
            #          ',mac=' + mac_hash(conf['img'], i)
            # conf['nic'].append((netdev, device))
            nic = gen_virtio_dev(conf['img'], i)
            conf['nic'].append(nic)
        conf['vnc_port'] = str(vnc_port)
        vnc_port += 1

def cfg_parser():
    """
    parsing the config file
    """
    # TODO try more dirs
    dir = './'
    cf = dir + 'vm.cfg'
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


class VM(object):
    """
    modelling a QEMU/KVM virtual machine
    """
    def __init__(self, name, conf):
        """
        name is a string
        conf is the config for this specific VM
        """
        self.conf = conf
        self.name = name

    def run(self):
        """
        bring the VM up
        """
        conf = self.conf
        qemu_cmd = conf['qemu'] + ' --enable-kvm' + ' -nographic' + \
                   ' -m ' + conf['memory'] + ' -cpu ' + conf['cpu'] + \
                   ' -smp ' + conf['smp'] + ' -hda ' +  conf['img'] + \
                   ' ' + ' '.join(conf['nic']) + ' -vnc :' + conf['vnc_port']
        if dry_run:
            print(qemu_cmd)
        else:
            pass

def test():
    cfgs = cfg_parser()
    for cfg in cfgs:
        if cfg in ('env', 'global'): continue
        vm = VM(cfg, cfgs[cfg]) 
        vm.run()

if __name__ == '__main__':
    # start_vm()
    test()
