from ranger.api.commands import *


def importFromParent(path, module):
    import os, sys
    if not os.path.isdir(path):
        path = os.path.dirname(path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    add = path in sys.path

    if add:
        sys.path.append(path)

    r = __import__(module)

    if add:
        sys.path.pop()

    return r


class _superCommand(Command):
    '''
    base class for commands which modify some sub command
    '''
    def __init__(self, *args, **kwargs):
        Command.__init__(self, *args, **kwargs)

        self.__subCmd = None

    def _getSubLine(self):
        flags, rest = self.parse_flags()
        return rest

    def _getSubCommand(self):
        if self.__subCmd is not None:
            return self.__subCmd

        line = self._getSubLine()
        try:
            cls = self.fm.commands.get_command(line.split()[0])
        except (KeyError, ValueError, IndexError):
            return
        self.__subCmd = r = cls(line)
        return r

    def quick(self):
        cmd = self._getSubCommand()
        if cmd is None:
            return None
        return cmd.quick()

    def execute(self):
        cmd = self._getSubCommand()
        if cmd is None:
            return None
        return cmd.execute()

    def cancel(self):
        cmd = self._getSubCommand()
        if cmd is None:
            return None
        return cmd.cancel()

    def tab(self):
        cmd = self._getSubCommand()
        if cmd is None:
            return None
        r = cmd.tab()
        if r is None:
            return r
        name = type(self).__name__
        return ('{} {}'.format(name, sub) for sub in r)


