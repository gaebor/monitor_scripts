#!/usr/bin/python3
import http.server
import socketserver
from http import HTTPStatus
from socket import gethostname
import subprocess

import argparse

import datetime
import io
import mimetypes
import sys
import time
import shutil

import urllib.parse

def check_output(command):
    return subprocess.run(command, 
                stdout=subprocess.PIPE,
                shell=True,
                universal_newlines=True).stdout

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
            r.append('<h1>Monitor {}</h1>'.format(gethostname()))
            
            r.append('<br>'.join(check_output("monitor_cpu -i").split('\n')))
            r.append(check_output("(echo -n _; free -h) | htmltable -c 6 -head 'class=tt'"))
            
            r.append('<h2 class="rolldownheader">Processes</h2>')
            r.append(check_output(
                        "ps -a -o '%mem,%cpu,uname,command' --sort '-%cpu' | "
                        " grep -vP ' *\d+\.\d+ +\d+\.\d+ +root' | "
                        "htmltable -c 3 -head 'class=tt'"))
            
            r.append('<h2 class="rolldownheader">Storage</h2>')
            r.append(check_output(
                        "df -h --output=source,used,avail,size,pcent | "
                        "grep -v '\s0%$' | "
                        "htmltable -c 4 -head 'class=tt'"))
            
            r.append('<h2 class="rolldownheader">Disk I/O</h2>')
            r.append(check_output(
                        "monitor_disk -s -F -i | htmltable -c 4 -head 'class=tt'"))
 
            r.append('<div class="rolldown">')
            r.append('<h2 class="rolldownheader">ZFS</h2>')
            r.append('<div class=rolldowncontent>')
            r.append('<pre>')
            r.append(check_output("zpool status"))
            r.append('</pre>')
            r.append('</div></div>')
            r.append('</body></html>')
            return '\n'.join(r)

    def __init__(self, *args, **kwargs):
        # print(args, kwargs)
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
        # print(self.headers)
        if requested_path == '/':
            try:
                content = self.assemble_html_content()
            except Exception as e:
                print(e, file=sys.stderr)
            else:
                return self.send_html_content(content)
        elif requested_path == "/network":
            content = check_output("iftop -t -s 1 2>&1")
            return self.send_html_content("<PRE>" + content + "</PRE>")
        # elif requested_path == '/favicon.ico':
            # return open('/home/gaebor/MI.ico', 'rb')
        
def main(args):
    print(MemoryHTTPRequestHandler.server_version)
    httpd = socketserver.TCPServer(("", args.port), MemoryHTTPRequestHandler)
    httpd.serve_forever()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument('-p', '--port', dest="port", type=int, default=8000)

    exit(main(parser.parse_args()))
