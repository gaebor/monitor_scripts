#!/bin/bash

if [[ " ${*} " == *" -h "* ]]; then
    echo script for monitoring the cpu and memory usage
    echo flags:
    echo -e "\t-h\thelp"
    echo -e "\t-b\tshow busiest worker"
    echo -e "\t-c\tshow # of cores"
    echo -e "\t-i\tshow cpu info in the first line"
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

if [[ " ${*} " == *" -i "* ]]; then
    grep "model name" /proc/cpuinfo | cut -f2 -d":" | while read line
    do
        echo $line | column
    done | uniq -c | sed "s/^ \+//"
fi

# ps -Ao pcpu,rsz,fname,uname | tail -n+2 | sort -rgk1 | collapse |

mem_str=`free -b | head -n 2 | tail -n 1 | python2 -c "import sys; print ' '.join(sys.stdin.readline().strip().split()[1:3])"`

top -n1 -b | \
python -c "
from __future__ import print_function
import sys

def to8(s):
    return s[:8]

sys.stdin.readline() # header
sys.stdin.readline() # tasks
sys.stdin.readline() # cpu
sys.stdin.readline() # mem

mem_total, sum_mem = map(int, '$mem_str'.split())

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

high_proc_str = ('(%-8s %-8s)' % tuple(high_proc_str)) if $high_usage else ''
high_mem_str  = ('(%-8s %-8s)' % tuple(high_mem_str) ) if $high_usage else ''
cores_str = ('%-4s' % '/$num_cores') if $show_cores else ''
print('%%%-5d' % sum_proc, cores_str, high_proc_str,
      sum_mem, '/', mem_total, high_mem_str)
"
