# Scripts for monitoring

## Tools

### `nvm`
bash script invokes `nvm.py` python2 script, reports gpu usage
#### Requirements
* bash
* python2
* [pynvml](https://pypi.python.org/pypi/nvidia-ml-py/)

### `monitor.sh`
bash script reports cpu and memory usage
#### Requirements
* bash
* python (2 or 3)
* free
* grep 
* `/proc/cpuinfo`
* top

### `monitor`
bash script calls `nvm` and `monitor.sh`
#### Requirements
* all of the above
* plus [hr](https://github.com/gaebor/human_readable)


The `disk_stat` uses a tmpfs for storing data between runs.
Create a small tmpfs accessible to everyone:

    sudo mount -t tmpfs -o size=10M,mode=0777 tmpfs /home/.tmpfs
