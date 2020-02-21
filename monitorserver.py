import http.server
import socketserver
from http import HTTPStatus
from html import escape as htmlescape
from socket import gethostname
import subprocess, time, os, glob

import argparse
import datetime
import io
import sys
import shutil

import urllib.parse

def check_output(command):
    return subprocess.run(command, 
                stdout=subprocess.PIPE,
                shell=(type(command) == str),
                universal_newlines=True).stdout

ticks = int(check_output("""FILENAME=`tempfile`; echo '#include <unistd.h>
#include <stdio.h>
int main(){printf("%lu", sysconf(_SC_CLK_TCK)); return 0;}
' > $FILENAME.c && gcc -o $FILENAME $FILENAME.c && $FILENAME && rm $FILENAME $FILENAME.c"""))

pid_to_hue = 360/int(open('/proc/sys/kernel/pid_max').read().strip())
cpu_info = check_output("grep '^model name' /proc/cpuinfo | "
                        "cut -f2 -d':' | uniq -c | sed 's/^\s\+//'")
cpu_cores = len(check_output(["grep", "processor", "/proc/cpuinfo"]).strip().split("\n"))

def get_pid_time(pid=None):
    if type(pid) == int:
        filename = '/proc/' + str(pid) + '/stat'
    else:
        filename = '/proc/[0-9]*/stat'
    result = {}
    for file in glob.glob(filename):
        try:
            with open(file) as f:
                content = f.read().strip().split()
        except OSError as e:
            continue
        else:
            result[int(file.split('/')[2])] = (int(content[13]) + int(content[14]))/ticks
    return result

pid_times = {time.time(): get_pid_time()}

def update_pid_times(dt=60):
    global pid_times
    currenttime = time.time()
    pid_times[currenttime] = get_pid_time()
    for key in list(pid_times.keys()):
        if key < currenttime - dt and key in pid_times:
            del pid_times[key]

def compose_cpu_graph():
    height = cpu_cores*100
    result = '<svg width="300" height="{}">\n'.format(height+30)
    result += '<g transform="translate(15,10)">\n'
    result += ' <path stroke="black" stroke-width="2" fill=none d="M0 0 L0 {0} L240 {0}" />\n'.format(height)
    result += ' <text font-size="20" fill="black" stroke="none" text-anchor="middle" x="240" y="{0}" dy="20">{1}</text>\n'.format(height, time.strftime("%H:%m:%S"))
    result += ' <g font-size="15" fill="black" stroke="none">\n'
    result += '  <g text-anchor="end">\n'
    for i in range(1, cpu_cores+1):
        result += '   <text x="0" y="{0}" dx="-5">{1}</text>\n'.format((cpu_cores-i)*100, i)
    result += '  </g><g text-anchor="middle">\n'
    for i in range(-60, 0, 15):
        result += '   <text x="{0}" y="{1}" dy="16">{i}</text>\n'.format(240+i*4, height, i=i)
    result += ' <g>\n'
    result += '<g stroke="black" stroke-width="1" fill=none>\n'
    for i in range(1, cpu_cores+1):
        result += '   <path d="M-5 {0} L0 {0}" />\n'.format(height - i*100)
    for i in range(0, -60, -15):
        result += '   <path d="M{0} {1} L{0} {2}" />\n'.format(240+4*i, height+5, height)
    result += ' </g>\n'
    result += '</g>\n'
    result += 'Sorry, your browser does not support inline SVG.\n</svg>'
    """<svg width="300" height="230">
	<g transform="translate(15,10)">
    		<path stroke="black" stroke-width="2" fill=none d="M0 0 L0 200 L240 200" />
            <text font-size="20" fill="black" stroke="none" text-anchor="middle" x="240" y="200" dy="20">01:02:50</text>
            <g font-size="15" fill="black" stroke="none">
              <g text-anchor="end">
                <text x="0" y="0" dx="-5">2</text>
                <text x="0" y="100" dx="-5">1</text>
              </g>
              <g text-anchor="middle">
                <text x="0" y="200" dy="16">-60</text>
                <text x="60" y="200" dy="16">-45</text>
                <text x="120" y="200" dy="16">-30</text>
                <text x="180" y="200" dy="16">-15</text>
              </g>
            </g>
            <g stroke="black" stroke-width="1" fill=none>
            	<path d="M-5 0 L0 0" />
                <path d="M-5 100 L0 100" />
            </g>
            <g stroke="black" stroke-width="1" fill=none>
				<path d="M0 205 L0 200" />
				<path d="M60 205 L60 200" />
                <path d="M120 205 L120 200" />
                <path d="M180 205 L180 200" />
                <path d="M240 205 L240 200" />
            </g>
            <g>
            	<rect x="0" y="180" width="40" height="20" style="fill:hsl(10.0, 100%, 75%);stroke:none;" />
                <rect x="0" y="160" width="40" height="20" style="fill:hsl(80, 100%, 75%);stroke:none;" />
                <rect x="40" y="50" width="40" height="150" style="fill:hsl(240, 100%, 75%);stroke:none;" />
  			</g>
  	</g>
  Sorry, your browser does not support inline SVG.
</svg>"""
    return result

def get_proc_info(pid):
    try:
        with open('/proc/' + str(pid) + '/cmdline') as f:
            cmdline = f.read().strip('\0').split('\0')
        with open('/proc/' + str(pid) + '/stat') as f:
            parent = int(f.read().strip().split()[3])
        userid = os.stat("/proc/" + str(pid)).st_uid
    except OSError as e:
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

def get_sector_sizes():
    d={}
    for file in glob.glob("/sys/block/*/queue/hw_sector_size"):
        try:
            with open(file) as f:
                d[file.split("/")[3]] = int(f.read().strip())
        except OSError:
            pass
    return d
    
def get_disk_stat():
    with open('/proc/diskstats') as f:
        content = f.read().strip().split('\n')
    d = {}
    for line in content:
        line = line.split()
        d[line[2]] = (int(line[5]), int(line[9]))
    return d
                
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

    def assemble_html_content(self):
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
*.rolldown > *.rolldowncontent {
    max-height: 0;
    overflow: hidden;
    transition-property: max-height;
    transition: all 1s ease-in-out;
}
*.rolldown:hover *.rolldowncontent {
    max-height: 700px;
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
            r.append(compose_cpu_graph())
            r.append(htmltable(check_output(
                        ["ps", "-a", "-f", "-o", "%cpu,%mem,uid,command", "--sort", "-%cpu"]
                        # " | grep -vP '^ *\d+\.\d+ +\d+\.\d+ +0 '"
                        ),
                        'class=tt', head=True, columns=3))

            r.append('<h3>Memory</h3>')
            r.append(htmltable("*" + check_output(["free", "-h"]), 'class=tt', head=True, columns=6))
            
            r.append('<h2 class="rolldownheader">Storage</h2>')
            r.append(htmltable(check_output(
                                "df -h --output=source,used,avail,size,pcent | "
                                "grep -v '\s0%$' | "
                                "(read line; echo \"$line\"; sort -hrk4)"), 
                        'class=tt', head=True, columns=4))
            
            r.append('<h2 class="rolldownheader">Disk I/O</h2>')
            r.append(htmltable(check_output("monitor_disk -s -F -i"), 
                        'class=tt', head=True, columns=4))
 
            # time.strftime("%H:%m:%S")
            """
<svg width="1000" height="1000">
	<g transform="translate(20,20)">
            <g stroke="black" stroke-width="2" fill=none>
                  <path d="M0 0 L0 200 L240 200" />
            </g>
            <g font-size="15" fill="black" stroke="none" text-anchor="end">
                <text x="0" y="0" dx="-5">2</text>
                <text x="0" y="100" dx="-5">1</text>
            </g>
            <g font-size="15" fill="black" stroke="none" text-anchor="middle">
                <text x="0" y="200" dy="15">-60s</text>
                <text x="60" y="200" dy="15">-45s</text>
            </g>
            <g stroke="black" stroke-width="1" fill=none>
                  <path d="M-5 0 L0 0" />
                  <path d="M-5 100 L0 100" />
            </g>
            <g stroke="black" stroke-width="1" fill=none>
            	<path d="M60 205 L60 200" />
                <path d="M120 205 L120 200" />
                <path d="M180 205 L180 200" />
                <path d="M240 205 L240 200" />
            </g>
  			<g font-size="20" font-family="sans-serif" fill="black" stroke="none" text-anchor="left">
                  <text x="240" y="200">01:02:50</text>
            </g>
            <g>
            	<rect x="20" y="180" width="40" height="20" style="fill:hsl(10.0, 100%, 75%);stroke:none;" />
                <rect x="20" y="160" width="40" height="20" style="fill:hsl(80, 100%, 75%);stroke:none;" />
                <rect x="60" y="50" width="40" height="150" style="fill:hsl(240, 100%, 75%);stroke:none;" />
  			</g>
            <!-- <g stroke="none" fill=red>
                  <path d="M20 200 L20 100 L30 110 L40 90 L50 90 L60 120 L60 200" />
            </g> -->
  	</g>
            Sorry, your browser does not support inline SVG.
            </svg>
            """
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
        requested_path = urllib.parse.unquote(self.path)
        print(requested_path)
        if requested_path == '/':
            content = self.assemble_html_content()
            return self.send_html_content(content)
        elif requested_path.lower() == "/zfs":
            content = check_output("zpool status")
            return self.send_html_content("<PRE>" + content + "</PRE>")
        elif requested_path.lower() == "/network":
            content = check_output("iftop -t -s 1 2>&1")
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

