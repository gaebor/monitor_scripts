function provide_cpu_data() {
    grep '^cpu' /proc/stat | tail -n+2 | python3 -c 'import sys; print(" ".join(map(str, (sum(map(int, line.strip().split()[1:4])) for line in sys.stdin))))'
}

CPU_stats=(`provide_cpu_data`)
n_cpus=${#CPU_stats[*]}
TIME=`date +%s`
ticks=100

time_interval=2
# filler=`python3 -c "print('\u25AE', end='')"`
filler='|'

while true
do
    sleep $time_interval
    COLUMNS=`tput cols`
    WIDTH=$(($COLUMNS/$n_cpus))
    NEW_STAT=(`provide_cpu_data`)
    NEW_TIME=`date +%s`
    for i in `seq 0 $((n_cpus-1))`
    do
        usage=$(($WIDTH*(${NEW_STAT[$i]}-${CPU_stats[$i]})/($NEW_TIME-$TIME)/$ticks))
        for i in `seq 1 $usage`; do echo -n "$filler"; done
        for i in `seq $(($usage+1)) $WIDTH`; do echo -n ' '; done
    done
    echo
    CPU_stats=(${NEW_STAT[*]})
    TIME=$NEW_TIME
done
