#!/bin/bash

function print_bar() {
    width="$1"
    length="$2"
    text=`echo -n "$3"; bash -c "printf ' %.0s' {1..$width}"`
    text="${text::$width}"
    echo -n -e "\e[7m"
    echo -n "${text::$length}"
    echo -n -e "\e[27m"
    echo -n "${text:$length}"
}

function provide_cpu_data() {
    grep '^cpu' /proc/stat | tail -n+2 | \
    while read line
    do
        echo -n $((`cut -f2,3,4 -d' ' <<<"$line" | sed 's/ /+/g'`))
        echo -n ' '
    done
}

CPU_STAT=(`provide_cpu_data`)
n_cpus=`getconf _NPROCESSORS_ONLN`
TIME=`date +%s`
ticks=`getconf CLK_TCK`

time_interval=2

while true
do
    sleep $time_interval
    COLUMNS=`tput cols`
    WIDTH=$(($COLUMNS/$n_cpus))
    NEW_STAT=(`provide_cpu_data`)
    FREQS=(`grep MHz /proc/cpuinfo | cut -f2 -d: | tr '\n' ' '`)
    NEW_TIME=`date +%s`
    for i in `seq 0 $((n_cpus-1))`
    do
        usage=$(($WIDTH * (${NEW_STAT[$i]}-${CPU_STAT[$i]}) / ($NEW_TIME-$TIME) / $ticks))
        print_bar $WIDTH $usage ${FREQS[$i]}
    done
    echo
    CPU_STAT=(${NEW_STAT[*]})
    TIME=$NEW_TIME
done
