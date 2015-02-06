import os
import sys

def loadCommands(path):
    if not os.path.isabs(path):
        path = os.path.abspath( os.path.join(os.path.dirname(__file__), path) )
    add = path not in sys.path

    if add:
        sys.path.append(path)

    import _commands

    if add:
        sys.path.pop()

    return _commands

sw = loadCommands('./smith waterman')
scout = sw.scout

