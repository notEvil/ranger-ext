import ranger.core.loader as loader
import ranger.config.commands as commands

import shared

import os
import sys
import subprocess as sub
import threading
import rpcss

import shutil


class RpcServerManager(object):
    '''
    provides a rpc server.

    if necessary, spawns a subprocess hosting a rpc client.
    '''
    def __init__(self, sudo=False):
        self.Sudo = sudo

        self.RpcServer = None

    def getRpcServer(self):
        rpcServer = self.RpcServer
        if rpcServer is not None:
            try:
                rpcServer.pass_() # check if still alive
                return rpcServer
            except IOError, e:
                if getattr(e, 'errno', 0) != 32:
                    raise

        args = []
        if self.Sudo:
            args.append('sudo')
        path = os.path.join(os.path.dirname(__file__), 'client.py')
        args.extend([sys.executable, path])

        import __main__
        import ranger
        args.extend(['-p', ranger.arg.confdir, '-p', os.path.dirname(__main__.__file__)])

        proc = sub.Popen(args, stdin=sub.PIPE, stdout=sub.PIPE, bufsize=-1)
        io = rpcss.EncryptedIO(proc.stdout, proc.stdin)
        self.RpcServer = rpcServer = rpcss.RpcServer(io)

        return rpcServer

    def __del__(self):
        try: self.RpcServer.stop()
        except: pass


GlobalRpcServerManager = RpcServerManager()
GlobalSudoRpcServerManager = RpcServerManager(sudo=True)

ActiveRpcServerManager = None


def externalCall(f, externalF=None):
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


def externalIter(f, externalF=None, step=False):
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
        return _externalIter(ActiveRpcServerManager, externalF, args, kwargs, step)

    return g

def _externalIter(rpcServerManager, externalF, args, kwargs, step):
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


def externalProgress(f, externalF=None, delay=loader.Loader.seconds_of_work_time):
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
        return _externalProgress(ActiveRpcServerManager, externalF, args, kwargs, delay)

    return g

def _externalProgress(rpcServerManager, externalF, args, kwargs, delay):
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
        self.Stopped = False

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
                self._stopRpcClient()
                raise
            finally:
                ActiveRpcServerManager = t

            yield n

        self._stopRpcClient()

    def _stopRpcClient(self):
        rpcServer = self.RpcServerManager.getRpcServer()
        rpcServer.stop()
        self.Stopped = True

    def pause(self):
        if not self.Stopped:
            rpcServer = self.RpcServerManager.getRpcServer()
            rpcServer.setPause(True)

        return _CopyLoader.pause(self)

    def unpause(self):
        if not self.Stopped:
            rpcServer = self.RpcServerManager.getRpcServer()
            rpcServer.setPause(False)

        return _CopyLoader.unpause(self)

    def destroy(self):
        if not self.Stopped:
            self._stopRpcClient()

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
    prev = counter.Count
    last = None

    try:
        for xx in x:
            if counter.Count == prev:
                continue
            prev = counter.Count

            yield xx
            last = xx

        if xx is not last:
            yield xx

    finally:
        counter.Stop = True


def deferredf(module, name, fname):
    def g(*args, **kwargs):
        import importlib
        m = importlib.import_module(module)
        f = getattr(m, name)
        return deferred(f(*args, **kwargs))
    g.__module__ = __name__
    g.__name__ = fname
    return g

_shutil_gen_move = deferredf('ranger.ext.shutil_generatorized', 'move', '_shutil_gen_move')
_shutil_gen_copytree = deferredf('ranger.ext.shutil_generatorized', 'copytree', '_shutil_gen_copytree')
_shutil_gen_copy2 = deferredf('ranger.ext.shutil_generatorized', 'copy2', '_shutil_gen_copy2')


Backups = {} # module: name: f

def enableExternalCopy():
    import ranger.ext.shutil_generatorized as shutil_gen
    import ranger.core.actions as actions

    m = Backups.setdefault('shutil_gen', {})

    m.setdefault('move', shutil_gen.move)
    shutil_gen.move = externalProgress(shutil_gen.move, _shutil_gen_move)

    m.setdefault('copytree', shutil_gen.copytree)
    shutil_gen.copytree = externalProgress(shutil_gen.copytree, _shutil_gen_copytree)

    m.setdefault('copy2', shutil_gen.copy2)
    shutil_gen.copy2 = externalProgress(shutil_gen.copy2, _shutil_gen_copy2)

    Backups.setdefault('loader', {}).setdefault('CopyLoader', loader.CopyLoader)
    loader.CopyLoader = CopyLoader

    Backups.setdefault('actions', {}).setdefault('CopyLoader', actions.CopyLoader)
    actions.CopyLoader = CopyLoader

def disableExternalCopy():
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


def f(module, name, fname):
    def g(*args, **kwargs):
        import importlib
        m = importlib.import_module(module)
        f = getattr(m, name)
        return f(*args, **kwargs)
    g.__module__ = __name__
    g.__name__ = fname
    return g

_shutil_rmtree = f('shutil', 'rmtree', '_shutil_rmtree')
_os_remove = f('os', 'remove', '_os_remove')


def enableExternalDelete():
    import shutil
    import os

    Backups.setdefault('shutil', {}).setdefault('rmtree', shutil.rmtree)
    shutil.rmtree = global_(externalCall(shutil.rmtree, _shutil_rmtree))

    Backups.setdefault('os', {}).setdefault('remove', os.remove)
    os.remove = global_(externalCall(os.remove, _os_remove))

def disableExternalDelete():
    import shutil
    import os

    shutil.rmtree = Backups['shutil'].pop('rmtree')
    os.remove = Backups['os'].pop('remove')

