#!/bin/bash

n_cpus=`getconf _NPROCESSORS_ONLN`
ticks=`getconf CLK_TCK`

function float_eval() {
    LC_NUMERIC='' awk "BEGIN {print $@}"
}

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

function provide_disk_data() {
    if [ -z "$1" ]
    then CONDITION='^s'
    else CONDITION="$1"
    fi
    DISKSTAT=`cat /proc/diskstats`
    grep -P '\d+' /sys/block/*/queue/hw_sector_size | \
    tr ':' '/' | cut -f4,7 -d'/' | grep "$CONDITION" | \
    while read line
    do
        DISK=`cut -f1 -d'/' <<<"$line"`
        SECTOR=`cut -f2 -d'/' <<<"$line"`
        STATS=(`grep " $DISK " <<<"$DISKSTAT"`)
        echo -n "$DISK(r)" `float_eval ${STATS[5]}*$SECTOR/125000000` "$DISK(w)" `float_eval ${STATS[9]}*$SECTOR/125000000` ' ' # "${STATS[9]}"
    done
}

function provide_cpu_data() {
    if [ -z "$1" ]
    then DEVIDE_NCPU="/$n_cpus"
    fi

    grep '^cpu' /proc/stat | \
    if [ "$1" ]; then tail -n+2; else head -n 1; fi | \
    while read line
    do
        CORE_STATS=($line)
        echo -n ${CORE_STATS[0]} `float_eval "(${CORE_STATS[1]}+${CORE_STATS[2]}+${CORE_STATS[3]})$DEVIDE_NCPU/$ticks"` ' '
    done
}

function provide_net_data() {
    if [ -z "$1" ]
    then CONDITION='^\w+:'
    else CONDITION="$1"
    fi
    grep -P "$CONDITION" /proc/net/dev | \
    while read line
    do
        NAME=`cut -f1 -d: <<<"$line"`
        STATS=(`cut -f2 -d: <<<"$line"`)
        echo -n "$NAME(R)" `float_eval "${STATS[0]}/125000000"` "$NAME(T)" `float_eval "${STATS[8]}/125000000"` ' '
    done
}

function provide_memory_data() {
    MEM=(`free | grep '^Mem:'`)
    MEM_H=(`free -h| grep '^Mem:'`)
    echo -n "${MEM_H[2]}/${MEM_H[1]}" `float_eval "${MEM[2]}/${MEM[1]}"` ' '
}

PROVIDERS=()
for arg in "$@"
do
    if [ "${arg::1}" = '-' ]
    then
        PROVIDERS[$((${#PROVIDERS[*]}-1))]="${arg:1}"
    else
        PROVIDERS+=("$arg" '')
    fi
done

CPU_STAT=($(for i in `seq 0 2 $((${#PROVIDERS[*]}-1))`; do provide_${PROVIDERS[$i]}_data ${PROVIDERS[$(($i+1))]}; done))
TIME=`date +%s`

time_interval=2

while true
do
    sleep $time_interval

    NEW_STAT=($(for i in `seq 0 2 $((${#PROVIDERS[*]}-1))`; do provide_${PROVIDERS[$i]}_data ${PROVIDERS[$(($i+1))]}; done))
    NEW_TIME=`date +%s`
    
    COLUMNS=`tput cols`
    WIDTH=$(($COLUMNS/${#NEW_STAT[*]}*2))

    for i in `seq 1 2 $((${#NEW_STAT[*]}-1))`
    do
        usage=`float_eval "$WIDTH*(${NEW_STAT[$i]}-${CPU_STAT[$i]})/($NEW_TIME-$TIME)" | cut -f1 -d'.'`
        print_bar $WIDTH $usage "${NEW_STAT[$(($i-1))]}"
    done
    echo
    
    CPU_STAT=(${NEW_STAT[*]})
    TIME=$NEW_TIME
done
