'''
looks for swalign.

from imports everything.
'''

import os
import sys

## import swalign

# find module path
path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'swalign'))

if not os.path.exists(path):
    raise ImportError('swalign does not exist. Run setup_sw.sh')

# add path to sys path
add = path not in sys.path
if add:
    sys.path.append(path)

# import everything
from swalign import *

# undo
if add:
    sys.path.pop()

