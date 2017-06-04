#!/bin/bash

mem_total=`free -mb | tail -n+2 | head -n1 | collapse | cut -f2 -d" "`

num_cores=`grep -c ^processor /proc/cpuinfo`

high_usage=False
show_cores=False

if [[ " ${*} " == *" -h "* ]]; then
    high_usage=True
fi

if [[ " ${*} " == *" -c "* ]]; then
    show_cores=True
fi

ps -Ao pcpu,rsz,fname,uname | tail -n+2 | sort -rgk1 | collapse | \
python -c "
from __future__ import print_function
import sys
high_proc_str = sys.stdin.readline().strip().split()
high_mem_str = high_proc_str
sum_proc = float(high_proc_str[0])
sum_mem = int(high_proc_str[1])
high_mem = sum_mem
for line in sys.stdin:
    line = line.strip().split()
    line = [float(line[0]), int(line[1])] + line[2:]
    if line[1] > high_mem:
        high_mem = line[1]
        high_mem_str = line
    sum_proc += line[0]
    sum_mem += line[1]

high_proc_str = '%-19s' % ('(' + ' '.join(high_proc_str[2:]) + ')') if $high_usage else ''
high_mem_str = '%-19s' % ('(' + ' '.join(high_mem_str[2:]) + ')') if $high_usage else ''
cores_str = ('%-5s' % '/$num_cores') if $show_cores else ''
print('%'+ ('%-5d' % sum_proc), cores_str, high_proc_str,
      int(1024*sum_mem), '/', $mem_total, high_mem_str)
"
