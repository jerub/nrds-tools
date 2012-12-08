from distutils.core import setup
import py2exe
import os
import sys

sys.path.append('evelink-api')

if len(sys.argv) == 1:
  sys.argv.append('py2exe')

icon_resources = []
if os.path.exists('icon.ico'):
  icon_resources.append((1, "icon.ico"))

setup(windows=[{'script': 'KosLookupExe.py',
                'icon_resources': icon_resources}],
    options={'py2exe': {'dll_excludes': ['MSVCP90.dll'],
                        'bundle_files': 1}},
    zipfile=None)

