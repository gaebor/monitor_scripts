# for hints see https://softwarebakery.com/shrinking-images-on-linux

DEVICE=/dev/sdc

if [[ $1 ]]
then
    DEVICE=$1
fi

FOLDER=/mnt/Fury/BackUp

if [[ "$2" ]]
then
    FOLDER="$2"
fi

OUTPUTNAME="$FOLDER/`basename $DEVICE`_`date +"%Y_%m_%d"`"

echo "[ backing up $DEVICE to \"$OUTPUTNAME\""

PARTED_INFO="`sudo parted $DEVICE unit B p | sed "s/^\s\+//" | grep -v "^\s*$" | tail -n1 | sed "s/\s\+/\t/g"`"

echo "$PARTED_INFO"

# last partition
PARTITION=`cut -f1 <<< "$PARTED_INFO"`
if [[ -z $PARTITION ]]
then
    exit 1
fi

if [[ $3 ]]
then
    CUSTOMPARTITION=$3
else
    CUSTOMPARTITION=$PARTITION
fi

FULLPARTITION=$DEVICE$CUSTOMPARTITION

DISK_SIZE=`lsblk --output=NAME,SIZE -b -p | grep "^$DEVICE\s" | cut -d" " -f2-`
if [[ -z $DISK_SIZE ]]
then
    exit 1
fi

echo "[ checking partition $FULLPARTITION ]"
sudo e2fsck -f $FULLPARTITION
if [[ $? -ne 0 ]]
then 
    exit 1
fi

if [[ -e $OUTPUTNAME.tmp ]]
then
    echo "[ found \"$OUTPUTNAME.tmp\" ]"
else
    echo "[ make full backup ]"
    sudo dd status=progress if=$DEVICE bs=1M of=$OUTPUTNAME.tmp
    if [[ $? -ne 0 ]]
    then
        exit 1
    fi
fi

echo "[ shrink the last partition"
sudo resize2fs $FULLPARTITION -M 2>&1 | tee $OUTPUTNAME.log
if [[ $? -ne 0 ]]
then 
    exit 1
fi

# find out how much did it manage to shrink
# every variable is measured in Bytes
SHRINKED=`grep "(4k)" $OUTPUTNAME.log | tail -n1 | python -c "import sys; l=sys.stdin.readline().strip().split(); pos=l.index('(4k)'); print(int(l[pos-1])*4096)"`
if [[ -z $SHRINKED ]]
then
    exit 1
fi

START=`cut -f2 <<<"$PARTED_INFO" | cut -f1 -d"B"`

NEW_END=$((START + 1 + (105*SHRINKED)/100))
echo "[ resize $FULLPARTITION to $NEW_END bytes ]"
sudo parted $DEVICE unit B resizepart $PARTITION $NEW_END
if [[ $? -ne 0 ]]
then
exit 1
fi

# sudo partprobe
if [[ -e $OUTPUTNAME.img ]]
then
    echo "[ found \"$OUTPUTNAME.img\" ]"
else
    echo "[ make trimmed backup ]"
    sudo dd status=progress if=$DEVICE bs=1M of=$OUTPUTNAME.img \
        count=$(((NEW_END + 1048575) / 1048576))
    if [[ $? -ne 0 ]]
    then
        exit 1
    fi
fi

chmod 777 $OUTPUTNAME.*
# rm $OUTPUTNAME.tmp

echo "[ extend partition to the full disk ]"
DISK_SIZE=$((DISK_SIZE - 1))
until sudo parted $DEVICE unit B resizepart $PARTITION $DISK_SIZE
do
    DISK_SIZE=$((DISK_SIZE - 1))
done

sudo parted $DEVICE unit B p | sed "s/^\s\+//" | grep -v "^\s*$" | tail -n1 | sed "s/\s\+/\t/g"
if [[ $? -ne 0 ]]
then
exit 1
fi

echo "[ extend filesystem to the full disk ]"
sudo resize2fs $FULLPARTITION 2>&1 | tee -a $OUTPUTNAME.log

if [[ $? -ne 0 ]]
then
exit 1
else
echo "[ DONE ]"
fi
