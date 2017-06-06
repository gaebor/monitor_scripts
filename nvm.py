from __future__ import print_function
from pynvml import *
import argparse
from subprocess import check_output

def main(args):
    nvmlInit()
    deviceCount = nvmlDeviceGetCount()
    if args.device_index >= deviceCount:
        print("Invalid device index:", args.device_index, file=sys.stderr)
        return 1
    handle = nvmlDeviceGetHandleByIndex(args.device_index)
    gpu_info = nvmlDeviceGetUtilizationRates(handle)
    mem_info = nvmlDeviceGetMemoryInfo(handle)

    processes = nvmlDeviceGetComputeRunningProcesses(handle)
    processes.sort(key=lambda info: info.usedGpuMemory, reverse=True)
    
    busiest = ['-', '-']
    if len(processes) > 0:
        busiest_pid = processes[0].pid
        pid_str = check_output(["ps", "--pid=%d" % busiest_pid, "-o", "fname,uname"])
        busiest = pid_str.split('\n')[1].strip().split()
        
    busiest_str = "(" + busiest[0] + " " + busiest[1] + ")"
    print('%' +  '%-5d' % gpu_info.gpu, mem_info.used, '/', mem_info.total,
          busiest_str if args.show_busiest else "")

    nvmlShutdown()
    return 0

parser = argparse.ArgumentParser(
                description="NVidia Monitoring tool",
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-d", "--device", dest="device_index", type=int, default=0,
                    help='device index')
parser.add_argument('-b', '--busiest', dest='show_busiest', 
                    default=False, action='store_true',
                    help='show busiest process and user')
parser.add_argument('-v', '--verbose', dest='verbose', 
                    default=False, action='store_true',
                    help='print driver, device informations to stderr')

exit(main(parser.parse_args()))