# Scripts for monitoring

## Requirements
* bash
* sysstat (iostat)
* bc
* free
* ps
* lsblk
* python2
* [hr](https://github.com/gaebor/human_readable)
* [rs](http://www.unix.com/man-page/FreeBSD/1/rs/)

The `disk_stat` uses a tmpfs for storing data between runs.
Create a small tmpfs accessible to everyone:

    sudo mount -t tmpfs -o size=10M,mode=0777 tmpfs /home/.tmpfs
