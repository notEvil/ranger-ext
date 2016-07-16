import ranger.api.commands as commands

class SuperCommand(commands.Command):
    '''
    base class for commands which modify some sub command
    '''
    def __init__(self, *args, **kwargs):
        commands.Command.__init__(self, *args, **kwargs)

    def createSubCommand(self):
        line = self.parse_flags()[1]
        if len(line) == 0:
            return None
        try:
            cmd = self.fm.commands.get_command(line.split()[0])
        except KeyError:
            return None
        return cmd(line)

    def _delegate(name):
        def g(self, *args, **kwargs):
            cmd = self.createSubCommand()
            if cmd is None:
                return None
            f = getattr(cmd, name)
            return f(*args, **kwargs)
        return g

    quick = _delegate('quick')
    execute = _delegate('execute')
    cancel = _delegate('cancel')

    def tab(self, *args, **kwargs):
        cmd = self.createSubCommand()
        if cmd is None:
            return None
        r = cmd.tab(*args, **kwargs)
        if r is None:
            return None
        name = type(self).__name__
        if isinstance(r, str):
            return '{} {}'.format(name, r)
        return ('{} {}'.format(name, sub) for sub in r)

