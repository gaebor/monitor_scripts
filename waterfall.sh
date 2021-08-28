#!/bin/bash

n_cpus=`getconf _NPROCESSORS_ONLN`
ticks=`getconf CLK_TCK`

function float_eval() {
    LC_ALL='C' awk "BEGIN {print $@}"
}

function float_eval_round() {
    LC_ALL='C' awk "BEGIN { printf(\"%.0f\n\", $@); }"
}

function print_bar() {
    width=`float_eval_round "$1"`
    text=`echo -n "$2"; bash -c "printf ' %.0s' {1..$width}"`
    text="${text::$width}"
    major=`float_eval_round "$width*$3"`
    minor=`float_eval_round "$width*$4"`
    echo -n -e "\e[7m"
    echo -n "${text::$major}"
    echo -n -e "\e[27m\e[41m"
    echo -n "${text:$major:$minor}"
    echo -n -e "\e[49m"
    echo -n "${text:$(($major+$minor))}"
}

function provide_disk_data() {
    if [ -z "$1" ]
    then CONDITION=' [a-z]+ '
    else CONDITION="$1"
    fi
    SECTOR_SIZES=`grep '' /sys/block/*/queue/hw_sector_size | tr ':' '/' | cut -f4,7 -d'/'`
    grep -P "$CONDITION" /proc/diskstats | \
    while read line
    do
        STATS=($line)
        NAME="${STATS[2]}"
        SECTOR_SIZE=`grep "${NAME::3}" <<<"$SECTOR_SIZES" | cut -f2 -d'/'`
        if [ -z "$SECTOR_SIZE" ]
        then 
            SECTOR_SIZE=512
        fi
        echo -n "$NAME" `float_eval ${STATS[5]}*$SECTOR_SIZE/125000000` `float_eval ${STATS[9]}*$SECTOR_SIZE/125000000` ' '
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
        echo -n ${CORE_STATS[0]} `float_eval "(${CORE_STATS[1]}+${CORE_STATS[2]})$DEVIDE_NCPU/$ticks"` `float_eval "(${CORE_STATS[3]})$DEVIDE_NCPU/$ticks"` ' '
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
        echo -n "$NAME" `float_eval "${STATS[0]}/125000000"` `float_eval "${STATS[8]}/125000000"` ' '
    done
}

function provide_memory_data() {
    MEM=(`free | grep '^Mem:'`)
    MEM_H=(`free -h| grep '^Mem:'`)
    echo -n "${MEM_H[2]}/${MEM_H[1]}" `float_eval "${MEM[2]}/${MEM[1]}"` `float_eval "${MEM[5]}/${MEM[1]}"`
}

SHOW_MEM=''
PROVIDERS=()
for arg in "$@"
do
    if [ "${arg::1}" = '-' ]
    then
        PROVIDERS[$((${#PROVIDERS[*]}-1))]="${arg:1}"
    else
        if [ "$arg" = 'memory' ]
        then
            SHOW_MEM=true
        else
            PROVIDERS+=("$arg" '')
        fi
    fi
done

CPU_STAT=($(for i in `seq 0 2 $((${#PROVIDERS[*]}-1))`; do provide_${PROVIDERS[$i]}_data "${PROVIDERS[$(($i+1))]}"; done))
TIME=`date +%s.%N`

time_interval=5

while true
do
    sleep $time_interval

    NEW_STAT=($(for i in `seq 0 2 $((${#PROVIDERS[*]}-1))`; do provide_${PROVIDERS[$i]}_data "${PROVIDERS[$(($i+1))]}"; done))
    NEW_TIME=`date +%s.%N`
    
    N_STATS=$((${#NEW_STAT[*]}/3))
    if [ "$SHOW_MEM" ]; then N_STATS=$(($N_STATS+1)); fi

    COLUMNS=`tput cols`
    WIDTH=$(($COLUMNS/$N_STATS))

    for i in `seq 0 3 $((${#NEW_STAT[*]}-1))`
    do
        usage1=`float_eval "(${NEW_STAT[$(($i+1))]}-${CPU_STAT[$(($i+1))]})/($NEW_TIME-$TIME)"`
        usage2=`float_eval "(${NEW_STAT[$(($i+2))]}-${CPU_STAT[$(($i+2))]})/($NEW_TIME-$TIME)"`
        print_bar $WIDTH "${NEW_STAT[$i]}" $usage1 $usage2 
    done

    if [ "$SHOW_MEM" ]
    then
        MEMORY_INFO=(`provide_memory_data`)
        print_bar $WIDTH "${MEMORY_INFO[0]}" `float_eval "${MEMORY_INFO[1]}"` `float_eval "${MEMORY_INFO[2]}"`
    fi
    echo
    
    CPU_STAT=(${NEW_STAT[*]})
    TIME=$NEW_TIME
done
