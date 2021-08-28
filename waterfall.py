import psutil
from time import sleep
from termcolor import colored
import math


def convert_size(size_bytes, table, base):
    if len(table) == 0 or base <= 0:
        raise ValueError("ERROR in convert_size")
    if size_bytes == 0:
        return "0" + table[0]
    i = min(int(math.log(size_bytes, base)), len(table) - 1)
    p = base ** i
    s = round(size_bytes / p, 2)
    return "{:g}{:s}".format(s, table[i])


def convert_size_2(bytes):
    return convert_size(bytes, ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"), 1024)


def convert_size_10(size):
    return convert_size(size, ("", "k", "M", "G", "T", "P", "E", "Z", "Y"), 1000)


def text_cap(s, width):
    if width == 0:
        return ''
    return f'{s[:width]:{width}s}'


def print_bar(text, highlight1_width, highlight2_width=0, total_width=80):
    total_width = int(max(0, total_width))
    highlight1_width = int(min(highlight1_width, total_width))
    highlight2_width = int(min(highlight2_width, total_width - highlight1_width))
    part1 = (
        colored(text_cap(text, highlight1_width), attrs=['reverse'])
        if highlight1_width > 0
        else ''
    )
    part2 = (
        colored(text_cap(text[highlight1_width:], highlight2_width), on_color='on_red',)
        if highlight2_width > 0
        else ''
    )
    part3 = text_cap(
        text[highlight1_width + highlight2_width :],
        total_width - (highlight1_width + highlight2_width),
    )

    print(part1 + part2 + part3, end='')


def get_cpu():
    cpu_times = {
        f'cpu{i:02d}': (cpu_time.user, 100 - cpu_time.idle - cpu_time.user)
        for i, cpu_time in enumerate(psutil.cpu_times_percent(percpu=True))
    }
    # cpu_additional = {f'cpu{i:02d}': x for i, x in enumerate(psutil.cpu_freq(percpu=True))}
    cpu_times['cpu'] = (
        sum(x[0] for x in cpu_times.values()),
        sum(x[1] for x in cpu_times.values()),
    )
    return cpu_times


def get_memory():
    memory_info = psutil.virtual_memory()
    return {
        'memory': (
            memory_info.percent,
            0,
            convert_size_2(memory_info.used) + '/' + convert_size_2(memory_info.total),
        )
    }


def print_column(infokey, infovalue, factor=1, width=10):
    print_bar(
        infovalue[2] if len(infovalue) > 2 else infokey,
        infovalue[0] / factor,
        infovalue[1] / factor,
        total_width=width,
    )


def main():
    while True:
        sleep(1)
        for k, v in get_cpu().items():
            if k != 'cpu':
                print_column(k, v, factor=10, width=10)
            else:
                n_cpu = psutil.cpu_count()
                print_column(k, v, factor=10 * n_cpu, width=10)
        for k, v in get_memory().items():
            print_column(k, v, factor=5, width=20)
        print('', flush=True)


if __name__ == '__main__':
    main()
