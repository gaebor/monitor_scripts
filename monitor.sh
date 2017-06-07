#!/bin/bash

if [[ " ${*} " == *" -h "* ]]; then
    echo script for monitoring the cpu and memory usage
    echo flags:
    echo -e "\t-h\thelp"
    echo -e "\t-b\tshow busiest worker"
    echo -e "\t-c\tshow # of cores"
    exit 0
fi

num_cores=`grep -c ^processor /proc/cpuinfo`

high_usage=False
show_cores=False

if [[ " ${*} " == *" -b "* ]]; then
    high_usage=True
fi

if [[ " ${*} " == *" -c "* ]]; then
    show_cores=True
fi

# ps -Ao pcpu,rsz,fname,uname | tail -n+2 | sort -rgk1 | collapse |
top -n1 -b | collapse | \
python -c "
from __future__ import print_function
import sys

def to8(s):
    return s[:8]

sys.stdin.readline() # header
sys.stdin.readline() # tasks
sys.stdin.readline() # cpu
line = sys.stdin.readline().strip().split(':')[1].split(',') # mem
memory_totals = list(map(lambda x: x.strip().replace('+', ' ').split()[0], line))
mem_total = int(memory_totals[0])
sum_mem = int(memory_totals[2])

sys.stdin.readline() # swap
sys.stdin.readline() #
sys.stdin.readline() # header

high_proc_str = ['-', '-']
high_mem_str = ['-', '-']

sum_proc = 0
high_proc = 0
high_mem = 0

for line in sys.stdin:
    line = line.strip().split()
    line = [float(line[8]), float(line[9]), line[-1], line[1]]
    if line[0] > high_proc:
        high_proc = line[0]
        high_proc_str = map(to8, line[2:])
    if line[1] > high_mem:
        high_mem = line[1]
        high_mem_str = map(to8, line[2:])
    sum_proc += line[0]

high_proc_str = '%-19s' % ('(' + ' '.join(high_proc_str) + ')') if $high_usage else ''
high_mem_str = '%-19s' % ('(' + ' '.join(high_mem_str) + ')') if $high_usage else ''
cores_str = ('%-5s' % '/$num_cores') if $show_cores else ''
print('%'+ ('%-5d' % sum_proc), cores_str, high_proc_str,
      int(1024*sum_mem), '/', mem_total, high_mem_str)
"
