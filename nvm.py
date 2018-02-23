from __future__ import print_function
import argparse
from subprocess import check_output

try:
    from py3nvml.py3nvml import *
except:
    from pynvml import *
    
def main(args):
    nvmlInit()
    
    busiest_gpu = 0
    gpu_usage = 0
    mem_usage = 0
    mem_total = 0
    
    num_devices = nvmlDeviceGetCount()
    for deviceCount in range(num_devices):
        handle = nvmlDeviceGetHandleByIndex(args.device_index)
        
        if args.info:
            print(nvmlDeviceGetName(handle))

        mem_info = nvmlDeviceGetMemoryInfo(handle)
        try:
            gpu_info = nvmlDeviceGetUtilizationRates(handle)
            gpu_info = gpu_info.gpu
        except:
            gpu_info = 0

        gpu_usage += 0        
        mem_usage += mem_info.used
        mem_total += mem_info.total
        
        busiest = ['-', '-']
        
        if busiest_gpu < gpu_info:
            busiest_gpu = gpu_info
            
            processes = nvmlDeviceGetComputeRunningProcesses(handle)
            processes.sort(key=lambda info: info.usedGpuMemory, reverse=True)
            
            if len(processes) > 0:
                busiest_pid = processes[0].pid
                pid_str = ""
                try:
                    pid_str = check_output(["ps", "--pid=%d" % busiest_pid, "-o", "fname,uname"]).split('\n')
                except:
                    busiest = ['?', '?']
                if len(pid_str) > 1:
                    busiest = pid_str[1].strip().split()
                
    busiest_str = "(%-8s %-8s)" % tuple(busiest)

    print('%%%-3d' % gpu_usage, mem_usage, '/', mem_total,
          busiest_str if args.show_busiest else "")

    nvmlShutdown()
    return 0

if __name__ == "__main__":
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
    parser.add_argument('-c', '--cpu', '--cores', dest='cpu',
                    default=False, action='store_true',
                    help='does nothing')
    parser.add_argument('-i', '--info', dest='info',
                    default=False, action='store_true',
                    help='prints device information')

    exit(main(parser.parse_args()))
