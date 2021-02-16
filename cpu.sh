CPU_stats=(`grep '^cpu' /proc/stat | tail -n+2 | python3 -c 'import sys; print(" ".join(map(str, (sum(map(int, line.strip().split()[1:4])) for line in sys.stdin))))'`)
n_cpus=${#CPU_stats[*]}
TIME=`date +%s`
ticks=100

while true
do
    sleep 2
    COLUMNS=`tput cols`
    WIDTH=$(($COLUMNS/$n_cpus))
    NEW_STAT=(`grep '^cpu' /proc/stat | tail -n+2 | python3 -c 'import sys; print(" ".join(map(str, (sum(map(int, line.strip().split()[1:4])) for line in sys.stdin))))'`)
    NEW_TIME=`date +%s`
    for i in `seq 0 $((n_cpus-1))`
    do
        usage=$(($WIDTH*(${NEW_STAT[$i]}-${CPU_stats[$i]})/($NEW_TIME-$TIME)/$ticks))
        # echo $usage
        for i in `seq 1 $usage`; do echo -n '#'; done
        for i in `seq $(($usage+1)) $WIDTH`; do echo -n ' '; done
    done
    echo 
    CPU_stats=(${NEW_STAT[*]})
    TIME=$NEW_TIME
done
