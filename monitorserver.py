import http.server
import socketserver
from http import HTTPStatus
from html import escape as htmlescape
from socket import gethostname
import subprocess, time, os, glob
from collections import OrderedDict

import argparse
import datetime
import io
import sys
import shutil

import urllib.parse
import math


def isbusy(disk):
    return (
        check_output(
            "sudo -n hdparm -C " + disk + " | grep 'drive state is: ' | tr ' ' '\\n' | tail -n1"
        ).strip()
        != "standby"
    )


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


def check_output(command, stderr=False):
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=(subprocess.STDOUT if stderr else None),
        shell=(type(command) == str),
        universal_newlines=True,
        check=False,
    ).stdout


ticks = int(
    check_output(
        """FILENAME=`tempfile`; echo '#include <unistd.h>
#include <stdio.h>
int main(){printf("%lu", sysconf(_SC_CLK_TCK)); return 0;}
' > $FILENAME.c && gcc -o $FILENAME $FILENAME.c && $FILENAME && rm $FILENAME $FILENAME.c"""
    )
)

pid_max = int(open('/proc/sys/kernel/pid_max').read().strip())
cpu_info = check_output(
    "grep '^model name' /proc/cpuinfo | " "cut -f2 -d':' | uniq -c | sed 's/^\s\+//'"
)
cpu_cores = len(check_output(["grep", "processor", "/proc/cpuinfo"]).strip().split("\n"))

sector_sizes = {}


def update_sector_sizes():
    global sector_sizes
    sector_sizes = {}
    for file in glob.glob("/sys/block/*/queue/hw_sector_size"):
        try:
            with open(file) as f:
                sector_sizes[file.split("/")[3]] = int(f.read().strip())
        except OSError:
            continue


update_sector_sizes()


def get_pid_times():
    result = {}
    for file in glob.glob('/proc/[0-9]*/stat'):
        try:
            with open(file) as f:
                content = f.read().strip().split()
        except OSError:
            continue
        else:
            result[int(file.split('/')[2])] = (int(content[13]) + int(content[14])) / ticks
    return OrderedDict((key, result[key]) for key in sorted(result))


def get_disk_activities():
    try:
        with open('/proc/diskstats') as f:
            content = f.read()
    except OSError:
        return {}
    result = {}
    for line in content.strip().split('\n'):
        line = line.split()
        if len(line) >= 14:
            if line[2] in sector_sizes:
                sector_size = sector_sizes[line[2]]
                result[line[2]] = (int(line[5]) * sector_size, int(line[9]) * sector_size)
    return OrderedDict((key, result[key]) for key in sorted(result))


class TimedDict:
    def __init__(self, f):
        self.updater = f
        self.d = OrderedDict({time.time(): f()})

    def update(self, dt=60, f=None):
        if f is None:
            f = self.updater
        currenttime = time.time()
        self.d[currenttime] = f()
        while len(self.d) > 0 and next(iter(self.d)) < currenttime - dt:
            del self.d[next(iter(self.d))]


class Report:
    def generate_html(self):
        return ''


class HistoryReport(Report):
    def __init__(self,):
        pass


class SnapshotReport(Report):
    pass


pid_times = TimedDict(get_pid_times)
disk_activities = TimedDict(get_disk_activities)


def query_to_type(q, t, default):
    try:
        if t == float:
            if len(q) == 1:
                return t(q[0])
            elif len(q) == 2:
                return t(q[0] + "." + q[1])
            else:
                return default
        elif t == int:
            return t(q[0])
        else:
            return q  # list of strings
    except:
        return default


def compose_cpu_graph(*args, timewindow=60, t_mul=4, y_mul=100, pid_mul=1, **kwargs):
    pid_mul = query_to_type(pid_mul, float, 1)
    timewindow = query_to_type(timewindow, float, 60)
    t_mul = query_to_type(t_mul, float, 4)
    y_mul = query_to_type(y_mul, float, 100)

    pid_times.update(dt=timewindow)

    height = cpu_cores * y_mul
    width = timewindow * t_mul

    timeticks = list(range(int(-timewindow), 0, int(timewindow / 4)))
    r = []
    r.append('<svg height="{}" width="{}">'.format(height + 30, width + 80))
    r.append('<g transform="translate(30,10)">')
    r.append(
        ' <path stroke="black" stroke-width="2" fill=none d="M0 0 L0 {0} L{1} {0}" />'.format(
            height, width
        )
    )
    r.append(
        ' <text font-size="20" fill="black" stroke="none" text-anchor="middle" x="{1}" y="{0}" dy="20">{2}</text>'.format(
            height, width, time.strftime("%H:%M:%S")
        )
    )
    r.append(' <g font-size="15" fill="black" stroke="none">')
    r.append('  <g text-anchor="end">')
    for i in range(1, cpu_cores + 1):
        r.append('   <text x="0" y="{0}" dx="-5">{1}</text>'.format((cpu_cores - i) * y_mul, i))
    r.append('  </g><g text-anchor="middle">')
    for i in timeticks:
        r.append(
            '   <text x="{0}" y="{1}" dy="16">{i}</text>'.format(
                (timewindow + i) * t_mul, height, i=i
            )
        )
    r.append(' <g>')
    r.append('<g stroke="black" stroke-width="1" fill=none>')
    for i in range(1, cpu_cores + 1):
        r.append('   <path d="M-5 {0} L0 {0}" />'.format(height - i * y_mul))
    for i in timeticks:
        r.append(
            '   <path d="M{0} {1} L{0} {2}" />'.format(
                t_mul * (timewindow + i), height + 5, height
            )
        )
    r.append(' </g>')
    if len(pid_times.d) > 1:
        r.append(' <g transform="scale(1, -1)"><g transform="translate(0,{})">'.format(-height))
        currenttime = timewindow - next(reversed(pid_times.d))
        pid_iter = iter(pid_times.d.items())
        previous_t, previous_pids = next(pid_iter)
        for t, pids in pid_iter:
            y = 0
            x = currenttime + previous_t
            dt = t - previous_t
            for pid in pids:
                dy = pids[pid]
                if pid in previous_pids:
                    dy -= previous_pids[pid]
                dy /= dt
                r.append(
                    '  <rect x="{x}" y="{y}" width="{w}" height="{h}" style="fill:hsl({hue}, 100%, 75%);stroke:none;" />'.format(
                        x=t_mul * x,
                        y=y_mul * y,
                        h=y_mul * dy,
                        w=t_mul * dt,
                        hue=pid_mul * pid * 360 / pid_max,
                    )
                )
                y += dy
            previous_t, previous_pids = t, pids
        r.append(' </g></g>')
    r.append('</g>')
    r.append('Sorry, your browser does not support inline SVG.')
    r.append('</svg>')
    return "\n".join(r)


def compose_io_graph(disk, *args, timewindow=60, t_mul=4, height=200, y_max=125000000, **kwargs):
    timewindow = query_to_type(timewindow, float, 60)
    t_mul = query_to_type(t_mul, float, 4)
    height = query_to_type(height, int, 200)
    y_max = query_to_type(y_max, float, 125000000)
    disk_activities.update(dt=timewindow)

    width = timewindow * t_mul
    timeticks = list(range(int(-timewindow), 0, int(timewindow / 4)))
    y_ticks = list(range(int(y_max), 0, -int(y_max / 4)))

    r = []
    r.append('<svg height="{}" width="{}">'.format(height + 30, width + 110))
    r.append('<g transform="translate(70,10)">')
    r.append(
        ' <path stroke="black" stroke-width="2" fill=none d="M0 0 L0 {0} L{1} {0}" />'.format(
            height, width
        )
    )
    r.append(
        ' <text font-size="20" fill="black" stroke="none" text-anchor="middle" x="{1}" y="{0}" dy="20">{2}</text>'.format(
            height, width, time.strftime("%H:%M:%S")
        )
    )
    r.append(' <g font-size="15" fill="black" stroke="none">')
    r.append('  <g text-anchor="end">')
    for i in y_ticks:
        r.append(
            '   <text x="0" y="{0}" dx="-7">{1}</text>'.format(
                height - i * height / y_max, convert_size_2(i)
            )
        )
    r.append('  </g><g text-anchor="middle">')
    for i in timeticks:
        r.append(
            '   <text x="{0}" y="{1}" dy="16">{i}</text>'.format(
                (timewindow + i) * t_mul, height, i=i
            )
        )
    r.append(' <g>')
    r.append('<g stroke="black" stroke-width="1" fill=none>')
    for i in y_ticks:
        r.append('   <path d="M-5 {0} L0 {0}" />'.format(i * height / y_max))
    for i in timeticks:
        r.append(
            '   <path d="M{0} {1} L{0} {2}" />'.format(
                t_mul * (timewindow + i), height + 5, height
            )
        )
    r.append(' </g>')
    if len(disk_activities.d) > 1:
        r.append(' <g transform="scale(1, -1)"><g transform="translate(0,{})">'.format(-height))
        currenttime = timewindow - next(reversed(disk_activities.d))
        disk_iter = iter(disk_activities.d.items())
        previous_t, previous_disks = next(disk_iter)
        x = currenttime + previous_t
        read_plot = '  <path style="fill:blue;fill-opacity:0.5;stroke:none;" d="M{} 0'.format(
            t_mul * x
        )
        write_plot = '  <path style="fill:red;fill-opacity:0.5;stroke:none;" d="M{} 0'.format(
            t_mul * x
        )
        for t, disks in disk_iter:
            dt = t - previous_t
            if disk in disks:
                y_read, y_write = disks[disk]
                if disk in previous_disks:
                    y_read -= previous_disks[disk][0]
                    y_write -= previous_disks[disk][1]
                y_read, y_write = y_read / dt, y_write / dt
            else:
                y_read, y_write = 0, 0
            read_plot += ' L{x1} {y} L{x2} {y}'.format(
                x1=t_mul * x, x2=t_mul * (x + dt), y=y_read * height / y_max
            )
            write_plot += ' L{x1} {y} L{x2} {y}'.format(
                x1=t_mul * x, x2=t_mul * (x + dt), y=y_write * height / y_max
            )
            previous_t, previous_disks = t, disks
            x += dt
        read_plot += 'L{} 0 Z" />'.format(width)
        write_plot += 'L{} 0 Z" />'.format(width)
        r.append(read_plot)
        r.append(write_plot)
        r.append('</g></g>')
    r.append('</g>')
    r.append('Sorry, your browser does not support inline SVG.')
    r.append('</svg>')
    return "\n".join(r)


def html_table_line(line, head=False, extra_attributes="", columns=3):
    if head:
        sep1 = '<th>'
        sep2 = '</th>'
    else:
        sep1 = '<td>'
        sep2 = '</td>'
    html_line = map(htmlescape, line.strip().split(None, columns))
    return f"<tr {extra_attributes}>{sep1}{(sep2 + sep1).join(html_line)}{sep2}</tr>"


def htmltable(text, *extra_attributes, head=False, columns=3):
    r = [f"<table {' '.join(extra_attributes)}>"]
    text = text.strip('\n').split('\n')
    if head and len(text) > 0:
        r.append(html_table_line(text[0], head=True, columns=columns))
        del text[0]
    for i, line in enumerate(text):
        r.append(
            html_table_line(
                line,
                extra_attributes='style="background-color: lightgrey;"' if i % 2 == 0 else '',
                columns=columns,
            )
        )

    r.append('</table>')
    return '\n'.join(r)


class MemoryHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    server_version = "MemoryHTTP/" + http.server.__version__
    enc = "utf-8"
    extensions_map = {'': 'application/octet-stream'}

    def send_html_content(self, content):
        if type(content) == str:
            encoded = content.encode(self.enc)
            f = io.BytesIO()
            f.write(encoded)
            f.seek(0)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", "text/html; charset={}".format(self.enc))
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            return f

    def assemble_main_page(self):
        r = []
        r.append('<!DOCTYPE HTML>')
        r.append('<html><head>')
        if "refresh" in self.query:
            r.append("<meta http-equiv=refresh content={}>".format(self.query["refresh"][0]))
        r.append('<meta charset="{}">'.format(self.enc))
        r.append('<title>{}</title>'.format(gethostname()))
        r.append('<style>')
        r.append(
            """table.tt * {
    font-family: monospace;
    border: 1px solid black;
}
table.tt{
    border: 2px solid black;
    border-collapse: collapse;
}
*.rolldown *.rolldownheader {
    border-bottom: 1px dotted grey;
    transition-property: border-bottom;
}
*.rolldown *.rolldowncontent {
    max-height: 0;
    overflow: hidden;
    transition-property: max-height;
    transition: all 1s ease-in-out;
}
*.rolldown:hover *.rolldowncontent {
    max-height: 700px;
    overflow-y: auto;
}
*.rolldown:hover *.rolldownheader {
    border-bottom: 1px hidden;
}
"""
        )
        r.append('</style>')
        r.append('</head>')
        r.append('<body>')
        r.append('<h1>{}</h1>'.format(gethostname()))

        if "vertical" in self.query:
            r.append('<h2 class="rolldownheader">CPU</h2>')
            r.append('<p>')
            r.append(cpu_info)
            r.append('</p>')
            r.append(compose_cpu_graph(**self.query))

            r.append('<h2>Memory</h2>')
            r.append(
                htmltable("*" + check_output(["free", "-h"]), 'class=tt', head=True, columns=6)
            )
        else:
            r.append('<table><tr>')
            r.append('<th>')
            r.append(cpu_info)
            r.append('</th>')
            r.append('<th>Memory</th>\n</tr>\n<tr>\n<td>')
            r.append(compose_cpu_graph(**self.query))
            r.append('</td>\n<td>')
            r.append(
                htmltable("*" + check_output(["free", "-h"]), 'class=tt', head=True, columns=6)
            )
            r.append('</td>\n</tr></table>')

        pid_percents = check_output(
            ["ps", "-a", "-f", "-o", "%cpu,%mem,uid,command", "--sort", "-%cpu"]
        )
        pid_percents = "\n".join(
            pid for pid in pid_percents.strip("\n").split("\n") if pid.split()[2] != "0"
        )

        r.append('<div class="rolldown">')
        r.append('<h3 class="rolldownheader">ps</h3>')
        r.append('<div class=rolldowncontent>')
        r.append(htmltable(pid_percents, 'class=tt', head=True, columns=3))
        r.append('</div></div>')

        r.append('<h2>Disk I/O</h2>')
        update_sector_sizes()
        forbidden_disks = [] if "exclude" not in self.query else self.query["exclude"]
        devices = [
            device
            for device in sector_sizes
            if not any(name in device for name in forbidden_disks)
        ]
        devices.sort()
        if "vertical" in self.query:
            for device in devices:
                r.append(
                    '<h3 style="color:{1}">{0}</h3>'.format(
                        device, "black" if isbusy("/dev/" + device) else "grey"
                    )
                )
                r.append(compose_io_graph(device, **self.query))
        else:
            r.append('<table><tr>')
            for device in devices:
                r.append(
                    '<th style="color:{1}">{0}</th>'.format(
                        device, "black" if isbusy("/dev/" + device) else "grey"
                    )
                )
            r.append('</tr><tr>')
            for device in devices:
                r.append('<td>')
                r.append(compose_io_graph(device, **self.query))
                r.append('</td>')
            r.append('</tr></table>')

        r.append('<h2 class="rolldownheader">Storage</h2>')
        r.append(
            htmltable(
                check_output(
                    "df -h --output=source,target,used,avail,size,pcent | "
                    "grep -v '\s0%$' | "
                    "(read line; echo \"$line\" | sed 's#Mounted on#Mounted_on#'; sort -hrk5)"
                ),
                'class=tt',
                head=True,
                columns=5,
            )
        )

        r.append('<div class="rolldown">')
        r.append('<h3 class="rolldownheader">zpool</h3>')
        r.append('<div class=rolldowncontent>')
        r.append("<pre>" + check_output("sudo -n zpool status") + "</pre>")
        r.append('</div></div>')

        r.append('</body></html>')
        return '\n'.join(r)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_GET(self):
        f = self.send_head()
        if f:
            try:
                shutil.copyfileobj(f, self.wfile)
            finally:
                f.close()

    def do_HEAD(self):
        f = self.send_head()
        if f:
            f.close()

    def send_head(self):
        parsed_request = urllib.parse.urlparse(urllib.parse.unquote(self.path))
        self.query = urllib.parse.parse_qs(parsed_request.query)
        requested_path = parsed_request.path

        if requested_path == '/':
            content = self.assemble_main_page()
            return self.send_html_content(content)
        elif requested_path.lower() == "/zfs":
            content = check_output("zpool status", True)
            return self.send_html_content("<PRE>" + content + "</PRE>")
        elif requested_path.lower() == "/network":
            content = check_output("iftop -t -s 1", True)
            return self.send_html_content("<PRE>" + content + "</PRE>")
        elif requested_path == '/favicon.ico' and os.path.isfile(args.icon):
            return open(args.icon, 'rb')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Process some integers.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('-p', '--port', dest="port", type=int, default=80, help=" ")
    parser.add_argument(
        '-f',
        "-i",
        '--favicon',
        "--icon",
        dest="icon",
        type=str,
        default="",
        help="path to favicon file",
    )
    args = parser.parse_args()

    print(MemoryHTTPRequestHandler.server_version)
    httpd = socketserver.TCPServer(("", args.port), MemoryHTTPRequestHandler)
    httpd.serve_forever()

