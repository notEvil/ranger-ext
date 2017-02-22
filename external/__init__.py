import ranger.core.loader as loader
import ranger.config.commands as commands

import shared

import os
import sys
import subprocess as sub
import threading
from . import rpcss

import shutil


class RpcServerManager(object):
    '''
    provides a rpc server.

    if necessary, spawns a subprocess hosting a rpc client.
    '''
    def __init__(self, sudo=False):
        self.Sudo = sudo

        self._Process = None
        self.RpcServer = None

    def getRpcServer(self):
        rpcServer = self.RpcServer
        if rpcServer is not None:
            try:
                rpcServer.pass_() # check if still alive
            except IOError as e:
                if getattr(e, 'errno', 0) != 32:
                    raise
            else:
                return rpcServer

        args = []
        if self.Sudo:
            args.append('sudo')
        path = os.path.join(os.path.dirname(__file__), 'client.py')
        args.extend([sys.executable, path])

        import __main__
        import ranger
        args.extend(['-p', ranger.arg.confdir, '-p', os.path.dirname(__main__.__file__)])

        self._Process = proc = sub.Popen(args, stdin=sub.PIPE, stdout=sub.PIPE, bufsize=-1)
        io = rpcss.EncryptedIO(proc.stdout, proc.stdin)
        self.RpcServer = rpcServer = rpcss.RpcServer(io)

        return rpcServer

    def stop(self):
        rpcServer = self.RpcServer
        if rpcServer is None:
            return
        self.RpcServer = None

        rpcServer.stop()
        rpcServer.IO.OutStream.close() # sends eof
        rpcServer.IO.InStream.close() # usually blocks until process terminates
        self._Process.wait() # to be save

    def __del__(self):
        self.stop()


GlobalRpcServerManager = RpcServerManager()
GlobalSudoRpcServerManager = RpcServerManager(sudo=True)

ActiveRpcServerManager = None


def call(f, externalF=None):
    '''
    decorator for external function calls.

    if ActiveRpcServerManager is None: calls f directly
    else: calls externalF (or f if externalF is None) using ActiveRpcServerManager.

    see rpcss.RpcServer.call.
    '''
    if externalF is None:
        externalF = f
    def g(*args, **kwargs):
        if ActiveRpcServerManager is None:
            return f(*args, **kwargs)
        rpcServer = ActiveRpcServerManager.getRpcServer()
        return rpcServer.call(externalF, args, kwargs)

    return g


def iter(f, externalF=None, step=False):
    '''
    decorator for external iterator/generator call.

    if ActiveRpcServerManager is None: calls f directly
    else: calls externalF (or f if externalF is None) using ActiveRpcServerManager.

    see rpcss.RpcServer.call_iter and rpcss.RpcServer.call_step.
    '''
    if externalF is None:
        externalF = f
    def g(*args, **kwargs):
        if ActiveRpcServerManager is None:
            return f(*args, **kwargs)
        return _iter(ActiveRpcServerManager, externalF, args, kwargs, step)

    return g

def _iter(rpcServerManager, externalF, args, kwargs, step):
    '''
    calls RpcServerManager.getRpcServer on first next().
    '''
    rpcServer = rpcServerManager.getRpcServer()
    if step:
        x = rpcServer.call_step(externalF, args, kwargs)
    else:
        x = rpcServer.call_iter(externalF, args, kwargs)

    for item in x:
        yield item


def progress(f, externalF=None, delay=loader.Loader.seconds_of_work_time):
    '''
    decorator for external non-blocking progress iterator/generator call.

    if ActiveRpcServerManager is None: calls f directly
    else: calls externalF (or f if externalF is None) using ActiveRpcServerManager.
    '''
    if externalF is None:
        externalF = f
    def g(*args, **kwargs):
        if ActiveRpcServerManager is None:
            return f(*args, **kwargs)
        return _progress(ActiveRpcServerManager, externalF, args, kwargs, delay)

    return g

def _progress(rpcServerManager, externalF, args, kwargs, delay):
    '''
    calls RpcServerManager.getRpcServer on first next().
    '''
    import time

    rpcServer = rpcServerManager.getRpcServer()
    x = rpcServer.call_iter(externalF, args, kwargs)

    current = next(x)
    yield current

    while True:
        time.sleep(delay)

        n = None
        while rpcServer.hasInput():
            try:
                n = next(x)
            except StopIteration:
                if n is not None:
                    yield n
                return

        if n is not None:
            current = n

        yield current


Sudo = False


def sudo_(f):
    '''
    decorator that sets Sudo to True during call.
    '''
    def g(*args, **kwargs):
        global Sudo
        Sudo = True
        try:
            r = f(*args, **kwargs)
        finally:
            Sudo = False

        return r

    return g


def global_(f, defaultRpcServerManager=None):
    '''
    decorator that sets ActiveRpcServerManager to defaultRpcServerManager or GlobalSudoRpcServerManager.
    '''
    def g(*args, **kwargs):
        global ActiveRpcServerManager
        t = ActiveRpcServerManager
        if Sudo:
            ActiveRpcServerManager = GlobalSudoRpcServerManager
        else:
            ActiveRpcServerManager = defaultRpcServerManager

        try:
            r = f(*args, **kwargs)
        finally:
            ActiveRpcServerManager = t

        return r
    return g


class sudo(shared.SuperCommand):
    '''
    shared.SuperCommand that sets Sudo to True during quick, tab, execute and cancel.
    '''
    def __init__(self, *args, **kwargs):
        shared.SuperCommand.__init__(self, *args, **kwargs)

    quick = sudo_(shared.SuperCommand.quick)
    tab = sudo_(shared.SuperCommand.tab)
    execute = sudo_(shared.SuperCommand.execute)
    cancel = sudo_(shared.SuperCommand.cancel)


_CopyLoader = loader.CopyLoader

class CopyLoader(_CopyLoader):
    '''
    sets ActiveRpcServerManager to self.RpcServerManager during each next().
    '''
    def __init__(self, *args, **kwargs):
        _CopyLoader.__init__(self, *args, **kwargs)

        self.RpcServerManager = RpcServerManager(sudo=Sudo)

    def generate(self):
        global ActiveRpcServerManager

        gen = _CopyLoader.generate(self)
        while True:
            t = ActiveRpcServerManager
            ActiveRpcServerManager = self.RpcServerManager

            try:
                n = next(gen)
            except StopIteration:
                break
            except Exception:
                self._stop()
                raise
            finally:
                ActiveRpcServerManager = t

            yield n

        self._stop()

    def _stop(self):
        self.RpcServerManager.stop()
        self.RpcServerManager = None

    def pause(self):
        if self.RpcServerManager is not None:
            rpcServer = self.RpcServerManager.getRpcServer()
            rpcServer.setPause(True)

        return _CopyLoader.pause(self)

    def unpause(self):
        if self.RpcServerManager is not None:
            rpcServer = self.RpcServerManager.getRpcServer()
            rpcServer.setPause(False)

        return _CopyLoader.unpause(self)

    def destroy(self):
        if self.RpcServerManager is not None:
            self._stop()

        return _CopyLoader.destroy(self)


class Counter(threading.Thread):
    '''
    threaded counter.
    '''

    Time = None

    def __init__(self, interval=1, autostart=True):
        threading.Thread.__init__(self)

        self.Interval = interval
        self.Autostart = autostart

        self.Count = 0
        self.Stop = False

        if Counter.Time is None:
            import time
            Counter.Time = time

        self.daemon = True

        if autostart:
            self.start()

    def run(self):
        while not self.Stop:
            Counter.Time.sleep(self.Interval)
            self.Count += 1


def deferred(x, interval=0.33):
    '''
    yields items of x only once in a while.

    uses Counter.
    '''
    counter = Counter(interval=interval)
    count = counter.Count
    prev = None

    try:
        n = None
        for n in x:
            if counter.Count == count:
                continue
            count = counter.Count

            yield n
            prev = n

        if n is not prev:
            yield n

    finally:
        counter.Stop = True


def _shutil_gen_move(*args, **kwargs):
    import ranger.ext.shutil_generatorized as m
    return deferred(m.move(*args, **kwargs))

def _shutil_gen_copytree(*args, **kwargs):
    import ranger.ext.shutil_generatorized as m
    return deferred(m.copytree(*args, **kwargs))

def _shutil_gen_copy2(*args, **kwargs):
    import ranger.ext.shutil_generatorized as m
    return deferred(m.copy2(*args, **kwargs))


Backups = {} # module: name: f

def enableCopy():
    '''
    replaces
        ranger.ext.shutil_generatorized
    .move,
    .copytree,
    .copy2,
        ranger.core.loader
    .CopyLoader,
        ranger.core.actions
    .CopyLoader
    '''
    import ranger.ext.shutil_generatorized as shutil_gen
    import ranger.core.actions as actions

    m = Backups.setdefault('shutil_gen', {})

    f = m.setdefault('move', shutil_gen.move)
    shutil_gen.move = progress(f, _shutil_gen_move)

    f = m.setdefault('copytree', shutil_gen.copytree)
    shutil_gen.copytree = progress(f, _shutil_gen_copytree)

    f = m.setdefault('copy2', shutil_gen.copy2)
    shutil_gen.copy2 = progress(f, _shutil_gen_copy2)

    Backups.setdefault('loader', {}).setdefault('CopyLoader', loader.CopyLoader)
    loader.CopyLoader = CopyLoader

    Backups.setdefault('actions', {}).setdefault('CopyLoader', actions.CopyLoader)
    actions.CopyLoader = CopyLoader

def disableCopy():
    import ranger.ext.shutil_generatorized as shutil_gen
    import ranger.core.actions as actions

    m = Backups['shutil_gen']
    shutil_gen.move = m.pop('move')
    shutil_gen.copytree = m.pop('copytree')
    shutil_gen.copy2 = m.pop('copy2')
    loader.CopyLoader = Backups['loader'].pop('CopyLoader')
    actions.CopyLoader = Backups['actions'].pop('CopyLoader')


class delete(commands.delete):
    '''
    stores Sudo on execute and sets Sudo during _question_callback.
    '''
    def __init__(self, *args, **kwargs):
        commands.delete.__init__(self, *args, **kwargs)

        self.Sudo = None

    def execute(self, *args, **kwargs):
        self.Sudo = Sudo

        return commands.delete.execute(self, *args, **kwargs)

    def _question_callback(self, *args, **kwargs):
        global Sudo
        Sudo = self.Sudo

        try:
            r = commands.delete._question_callback(self, *args, **kwargs)
        finally:
            Sudo = False

        return r


def _os_remove(*args, **kwargs):
    import os
    return os.remove(*args, **kwargs)

def _shutil_rmtree(*args, **kwargs):
    import shutil
    return shutil.rmtree(*args, **kwargs)


def enableDelete():
    '''
    replaces
        os
    .remove,
        shutil
    .rmtree
    '''
    import os
    import shutil

    f = Backups.setdefault('os', {}).setdefault('remove', os.remove)
    os.remove = global_(call(f, _os_remove))

    f = Backups.setdefault('shutil', {}).setdefault('rmtree', shutil.rmtree)
    shutil.rmtree = global_(call(f, _shutil_rmtree))

def disableDelete():
    import os
    import shutil

    os.remove = Backups['os'].pop('remove')
    shutil.rmtree = Backups['shutil'].pop('rmtree')


def _os_mkdir(*args, **kwargs):
    import os
    return os.mkdir(*args, **kwargs)

def _os_makedirs(*args, **kwargs):
    import os
    return os.makedirs(*args, **kwargs)


def enableMkdir():
    '''
    replaces
        os
    .makedirs,
    .mkdir,
    '''
    import os
    import ranger.config.commands as conf_commands

    f = Backups.setdefault('os', {}).setdefault('mkdir', os.mkdir)
    os.mkdir = global_(call(f, _os_mkdir))

    f = Backups.setdefault('os', {}).setdefault('makedirs', os.makedirs)
    os.makedirs = global_(call(f, _os_makedirs))

def disableMkdir():
    import os
    import ranger.config.commands as conf_commands

    os.mkdir = Backups['os'].pop('mkdir')
    os.makedirs = Backups['os'].pop('makedirs')


def _os_rename(*args, **kwargs):
    import os
    return os.rename(*args, **kwargs)


def enableRename():
    '''
    replaces
        os
    .rename

    ranger does not use os.renames.
    '''
    import os

    f = Backups.setdefault('os', {}).setdefault('rename', os.rename)
    os.rename = global_(call(f, _os_rename))

def disableRename():
    import os

    os.rename = Backups['os'].pop('rename')


def _os_symlink(*args, **kwargs):
    import os
    return os.symlink(*args, **kwargs)

def _relative_symlink(*args, **kwargs):
    import ranger.ext.relative_symlink
    return ranger.ext.relative_symlink.symlink(*args, **kwargs)

def _actions_symlink(*args, **kwargs):
    import ranger.core.actions
    return ranger.core.actions.symlink(*args, **kwargs)

def enableSymlink():
    '''
    replaces
        os
    .symlink,
        ranger.ext.relative_symlink
    .symlink,
        ranger.core.actions
    .symlink
    '''
    import os
    import ranger.ext.relative_symlink as relative_sym
    import ranger.core.actions as actions

    f = Backups.setdefault('os', {}).setdefault('symlink', os.symlink)
    os.symlink = global_(call(f, _os_symlink))

    f = Backups.setdefault('relative_sym', {}).setdefault('relative_symlink', relative_sym.symlink)
    relative_sym.symlink = global_(call(f, _relative_symlink))

    f = Backups.setdefault('actions', {}).setdefault('symlink', actions.symlink)
    actions.symlink = global_(call(f, _actions_symlink))

def disableSymlink():
    import os
    import ranger.ext.relative_symlink as relative_sym
    import ranger.core.actions as actions

    os.symlink = Backups['os'].pop('symlink')
    relative_sym.symlink = Backups['relative_sym'].pop('symlink')
    actions.symlink = Backups['actions'].pop('symlink')


def _os_link(*args, **kwargs):
    import os
    return os.link(*args, **kwargs)

def _actions_link(*args, **kwargs):
    import ranger.core.actions
    return ranger.core.actions.link(*args, **kwargs)


def enableHardlink():
    '''
    replaces
        os
    .link,
        ranger.core.actions
    .link
    '''
    import os
    import ranger.core.actions as actions

    f = Backups.setdefault('os', {}).setdefault('link', os.link)
    os.link = global_(call(f, _os_link))

    f = Backups.setdefault('actions', {}).setdefault('link', actions.link)
    actions.link = global_(call(f, _actions_link))

def disableHardlink():
    import os
    import ranger.core.actions as actions

    os.link = Backups['os'].pop('link')
    actions.link = Backups['actions'].pop('link')

