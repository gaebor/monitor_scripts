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

def check_output(command, stderr=False):
    return subprocess.run(command, 
                stdout=subprocess.PIPE,
                stderr=(subprocess.STDOUT if stderr else None),
                shell=(type(command) == str),
                universal_newlines=True, check=False).stdout

ticks = int(check_output("""FILENAME=`tempfile`; echo '#include <unistd.h>
#include <stdio.h>
int main(){printf("%lu", sysconf(_SC_CLK_TCK)); return 0;}
' > $FILENAME.c && gcc -o $FILENAME $FILENAME.c && $FILENAME && rm $FILENAME $FILENAME.c"""))

pid_max = int(open('/proc/sys/kernel/pid_max').read().strip())
cpu_info = check_output("grep '^model name' /proc/cpuinfo | "
                        "cut -f2 -d':' | uniq -c | sed 's/^\s\+//'")
cpu_cores = len(check_output(["grep", "processor", "/proc/cpuinfo"]).strip().split("\n"))

sector_sizes = {}

def update_sector_sizes():
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
            result[int(file.split('/')[2])] = (int(content[13]) + int(content[14]))/ticks
    return result

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
            result[line[2]] = (int(line[5]), int(line[9]))
            if line[2] in sector_sizes:
                result[line[2]] *= sector_sizes[line[2]]
    return result

class TimedDict:
    def __init__(self, f):
        self.updater = f
        self.d = OrderedDict({time.time(): f()})
    def update(self, dt=60):
        currenttime = time.time()
        self.d[currenttime] = self.updater()
        for key in list(self.d.keys()):
            if key < currenttime - dt and key in self.d:
                del self.d[key]

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
            return q # list of strings
    except:
        return default

def compose_cpu_graph(*args, timewindow=60, t_mul=4, y_mul=100, pid_mul=1, **kwargs):
    pid_mul = query_to_type(pid_mul, float, 1)
    timewindow = query_to_type(timewindow, float, 60)
    t_mul = query_to_type(t_mul, float, 4)
    y_mul = query_to_type(y_mul, float, 100)

    pid_times.update(dt=timewindow)
    
    height = cpu_cores*y_mul
    width = timewindow*t_mul
    r = []
    r.append('<svg height="{}" width="{}">'.format(height+30, width+80))
    r.append('<g transform="translate(30,10)">')
    r.append(' <path stroke="black" stroke-width="2" fill=none d="M0 0 L0 {0} L{1} {0}" />'.format(height, timewindow*t_mul))
    r.append(' <text font-size="20" fill="black" stroke="none" text-anchor="middle" x="{1}" y="{0}" dy="20">{2}</text>'.format(height, timewindow*t_mul, time.strftime("%H:%M:%S")))
    r.append(' <g font-size="15" fill="black" stroke="none">')
    r.append('  <g text-anchor="end">')
    for i in range(1, cpu_cores+1):
        r.append('   <text x="0" y="{0}" dx="-5">{1}</text>'.format((cpu_cores-i)*y_mul, i))
    r.append('  </g><g text-anchor="middle">')
    for i in range(int(-timewindow), 0, int(timewindow/4)):
        r.append('   <text x="{0}" y="{1}" dy="16">{i}</text>'.format((timewindow+i)*t_mul, height, i=i))
    r.append(' <g>')
    r.append('<g stroke="black" stroke-width="1" fill=none>')
    for i in range(1, cpu_cores+1):
        r.append('   <path d="M-5 {0} L0 {0}" />'.format(height - i*y_mul))
    for i in range(int(-timewindow), 0, int(timewindow/4)):
        r.append('   <path d="M{0} {1} L{0} {2}" />'.format(t_mul*(timewindow+i), height+5, height))
    r.append(' </g>')
    if len(pid_times.d) > 1:
        r.append('<g transform="scale(1, -1)"><g transform="translate(0,{})">'.format(-height))
        pid_times_sorted = list(pid_times.d.items())
        currenttime = timewindow - pid_times_sorted[-1][0]
        previous_t, previous_pids = pid_times_sorted[0]
        for t, pids in pid_times_sorted[1:]:
            y = 0
            x = currenttime + previous_t
            dt = t - previous_t
            for pid in sorted(pids):
                if pid in previous_pids:
                    dy = pids[pid] - previous_pids[pid]
                else:
                    dy = pids[pid]
                dy /= dt
                r.append('<rect x="{x}" y="{y}" width="{w}" height="{h}" style="fill:hsl({hue}, 100%, 75%);stroke:none;" />'.format(
                        x=t_mul*x, y=y_mul*y, h=y_mul*dy, w=t_mul*dt,
                        hue=pid_mul*pid*360/pid_max
                        ))
                y += dy
            previous_t, previous_pids = t, pids
        r.append('</g></g>')
    r.append('</g>')
    r.append('Sorry, your browser does not support inline SVG.')
    r.append('</svg>')
    return "\n".join(r)

def get_proc_info(pid):
    try:
        with open('/proc/' + str(pid) + '/cmdline') as f:
            cmdline = f.read().strip('\0').split('\0')
        with open('/proc/' + str(pid) + '/stat') as f:
            parent = int(f.read().strip().split()[3])
        userid = os.stat("/proc/" + str(pid)).st_uid
    except OSError:
        return {}
    else:
        return {"cmdline": cmdline, "user": userid, "parent": parent}

def htmltable(text, *extra, head=False, columns=3):
    r = ["<table " + " ".join(extra) + ">"]
    def formatline(line, head=False, extra=""):
        if head:
            sep1='<th>'
            sep2='</th>'
        else:
            sep1='<td>'
            sep2='</td>'
        r.append("<tr " + extra + ">" + sep1 + (sep2+sep1).join(map(htmlescape, line.strip().split(None, columns))) + sep2 + "</tr>")
        
    text = text.strip('\n').split('\n')
    if head and len(text) > 0:
        formatline(text[0], True)
        del text[0]
    for i, line in enumerate(text):
        formatline(line, False, 'style="background-color: lightgrey;"' if i%2==0 else "")

    r.append("</table>")
    return "\n".join(r)
                
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
    
            r.append('<meta charset="{}">'.format(self.enc))
            r.append('<title>{}</title>'.format(gethostname()))
            r.append('<style>')
            r.append("""table.tt * {
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
""")
            r.append('</style>')
            r.append('</head>')
            r.append('<body>')
            r.append('<h1>{}</h1>'.format(gethostname()))
            
            r.append('<h2 class="rolldownheader">CPU</h2>')
            r.append('<p>')
            r.append(cpu_info)
            r.append('</p>')
            r.append(compose_cpu_graph(**self.query))
            pid_percents = check_output(["ps", "-a", "-f", "-o", "%cpu,%mem,uid,command", "--sort", "-%cpu"])
            pid_percents = "\n".join(pid for pid in pid_percents.strip("\n").split("\n") if pid.split()[2] != "0")
            
            r.append('<div class="rolldown">')
            r.append('<h3 class="rolldownheader">ps</h3>')
            r.append('<div class=rolldowncontent>')
            r.append(htmltable(pid_percents, 'class=tt', head=True, columns=3))
            r.append('</div></div>')
            
            r.append('<h2>Memory</h2>')
            r.append(htmltable("*" + check_output(["free", "-h"]), 'class=tt', head=True, columns=6))
            
            r.append('<h2 class="rolldownheader">Storage</h2>')
            r.append(htmltable(check_output(
                                "df -h --output=source,target,used,avail,size,pcent | "
                                "grep -v '\s0%$' | "
                                "(read line; echo \"$line\" | sed 's#Mounted on#Mounted_on#'; sort -hrk5)"), 
                        'class=tt', head=True, columns=5))
            
            r.append('<h2 class="rolldownheader">Disk I/O</h2>')
            r.append(htmltable(check_output("monitor_disk -s -F -i"), 
                        'class=tt', head=True, columns=4))
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
    parser = argparse.ArgumentParser(description='Process some integers.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument('-p', '--port', dest="port", type=int, default=80, help=" ")
    parser.add_argument('-f', "-i", '--favicon', "--icon", dest="icon", 
                            type=str, default="", help="path to favicon file")
    args = parser.parse_args()
    
    print(MemoryHTTPRequestHandler.server_version)
    httpd = socketserver.TCPServer(("", args.port), MemoryHTTPRequestHandler)
    httpd.serve_forever()

