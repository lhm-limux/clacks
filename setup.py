#!/usr/bin/env python
import os
import sys
import shutil

modules = ['common',
    'agent',
    'dbus',
    'client',
    'shell',
    'utils']

for module in modules:
    os.system("cd %s && ./setup.py %s" % (module, " ".join(sys.argv[1:])))

for root, dirs, files in os.walk("plugins"):
    if "setup.py" in files:
        os.system("cd %s && ./setup.py %s" % (root, " ".join(sys.argv[1:])))

if 'clean' in sys.argv:
    docpath = os.path.abspath("./doc/html")
    if os.path.isdir(docpath):
        shutil.rmtree(docpath)
else:
    os.system("make -C doc html")
