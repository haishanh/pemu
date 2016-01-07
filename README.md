## pemu

`pemu` is a QEMU/KVM command line wrapper

**Note**: this tool is not intend to replace those powerful tools like libvirt or virtual manager. This tool will be handy only if you use bare QEUMU cli a lot.

### Usage

```sh
$ python pemu.py -h
usage: pemu.py [-h] [-d] [-f CONFIG_FILE]

Qemu wrapper

optional arguments:
  -h, --help            show this help message and exit
  -d, --dry-run         Dry run
  -f CONFIG_FILE, --config-file CONFIG_FILE
                        Specify config file(use ./vm.ini by defualt) 
```

You can supply a configuration file with option `-f`. If it is not specified the one named 'vm.ini' in the same directory of pemu.py will be used.

### Configuraion file

See `vm.ini` for detail.

For example the below configuration:

```text
[global]
qemu = qemu-system-x86_64 
memory = 3G
cpu = host
nic_nb = 2
base_vnc_port = 40

[arch]
nic_nb = 1
image = /home/haishanh/images/arch.qcow2
vnc_port = 80

[ubuntu]
image = /home/haishanh/images/ubuntu-1504-1.qcow2
extra = -monitor telnet:127.0.0.1:1234,server,nowait  -name ubuntu

[fakeone]
image = /path/to/a_fake_image.qcow2
```

Will yield:

```sh
$ python pemu.py -d
qemu-system-x86_64 \
-enable-kvm \
-nographic \
-m 3G \
-cpu host \
-smp cores=2,threads=1,sockets=1 \
-hda /home/haishanh/images/arch.qcow2 \
-netdev tap,id=hostnet0,script=no,downscript=no,vhost=on \
-device virtio-net-pci,netdev=hostnet0,mac=52:54:3e:cb:a7:12 \
-vnc :80 


qemu-system-x86_64 \
-enable-kvm \
-nographic \
-m 3G \
-cpu host \
-smp cores=2,threads=1,sockets=1 \
-hda /path/to/a_fake_image.qcow2 \
-netdev tap,id=hostnet0,script=no,downscript=no,vhost=on \
-device virtio-net-pci,netdev=hostnet0,mac=52:54:1d:90:1e:3d \
-netdev tap,id=hostnet1,script=no,downscript=no,vhost=on \
-device virtio-net-pci,netdev=hostnet1,mac=52:54:99:7e:7a:49 \
-vnc :41 


qemu-system-x86_64 \
-enable-kvm \
-nographic \
-m 3G \
-cpu host \
-smp cores=2,threads=1,sockets=1 \
-hda /home/haishanh/images/ubuntu-1504-1.qcow2 \
-netdev tap,id=hostnet0,script=no,downscript=no,vhost=on \
-device virtio-net-pci,netdev=hostnet0,mac=52:54:17:54:e0:b8 \
-netdev tap,id=hostnet1,script=no,downscript=no,vhost=on \
-device virtio-net-pci,netdev=hostnet1,mac=52:54:6b:b6:35:46 \
-vnc :40 \
-monitor telnet:127.0.0.1:1234,server,nowait  \
-name ubuntu
```

### License

Use it whatever you want.
