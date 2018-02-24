# for hints see https://softwarebakery.com/shrinking-images-on-linux

if [[ $1 ]]
then
    DEVICE=$1
fi

if [[ "$2" ]]
then
    FILE="$2"
fi

echo "[ restoring $DEVICE from \"$FILE\" ]"

DISK_SIZE=`lsblk --output=NAME,SIZE -b -p | grep "^$DEVICE\s" | cut -d" " -f2-`
if [[ -z "$DISK_SIZE" ]]
then
    exit 1
fi

sudo dd status=progress of=$DEVICE bs=1M if=$FILE
if [[ $? -ne 0 ]]
then
    exit 1
fi

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

echo "[ checking $FULLPARTITION ]"
sudo e2fsck -f $FULLPARTITION
if [[ $? -ne 0 ]]
then 
    exit 1
fi

echo "[ extend partition to the full disk ]"
DISK_SIZE=$((DISK_SIZE - 1))
until sudo parted $DEVICE unit B resizepart $PARTITION $DISK_SIZE
do
    DISK_SIZE=$((DISK_SIZE - 1))
done

echo "[ extend filesystem to the full disk ]"
sudo resize2fs $FULLPARTITION 2>&1
if [[ $? -ne 0 ]]
then
    exit 1
else
    echo "[ DONE ]"
fi
