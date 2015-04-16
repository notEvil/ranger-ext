# -*- coding: utf-8 -*-

from ranger.api.commands import *
import ranger.config.commands as commands

import ranger.core.loader as loader

import run_external
import time

import os
import sys
import shutil


def getParentPath():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

path = getParentPath()
add = path not in sys.path
if add:
    sys.path.append(path)
import shared
if add:
    sys.path.pop()



Sudo = False

def sudo_enabled(f):
    '''
    decorator. sets global Sudo to True before execution and back to False afterwards
    '''
    def _f(*args, **kwargs):
        global Sudo
        Sudo = True
        try:
            return f(*args, **kwargs)
        finally:
            Sudo = False
    return _f


class sudo(shared._superCommand):
    '''
    uses sudo_enabled to toggle global Sudo before handling the sub command
    '''
    def __init__(self, *args, **kwargs):
        shared._superCommand.__init__(self, *args, **kwargs)

    quick = sudo_enabled(shared._superCommand.quick)
    execute = sudo_enabled(shared._superCommand.execute)
    cancel = sudo_enabled(shared._superCommand.cancel)
    tab = sudo_enabled(shared._superCommand.tab)



class ExternalLoader(loader.Loadable, shared.FileManagerAware):
    '''
    useful construct that acts like a local Loader but initiates the external
    execution and handles communication.
    '''
    progressbar_supported = True
    def __init__(self, init, sudo, f, args=None, kwargs=None):
        self.Init = init
        self.Sudo = sudo
        self.F = f
        self.Args = tuple() if args is None else args
        self.Kwargs = {} if kwargs is None else kwargs

        importPaths = []
        import __main__
        importPaths.append( os.path.abspath(os.path.dirname(__main__.__file__)) )
        importPaths.append( getParentPath() )

        self.Interface = run_external.Interface(sudo=sudo, beforeSudo=self._beforeSudo, importPaths=importPaths)
        self.External = run_external.runExternal(self.Interface, self.F, self.Args, self.Kwargs)
        next(self.External)

        loader.Loadable.__init__(self, self.generate(), 'Executing {} externally ...'.format(f.__name__))

    def _beforeSudo(self):
        self.fm.execute_command('sudo echo -n')

    def generate(self):
        current = self.Init
        first = True
        for n in self.External:
            if n is None:
                if first:
                    time.sleep(0.033)
                    first = False
                    continue
                yield current
                first = True
                continue

            self.updateProgress(current)
            current = n
            yield n
            first = True

    def updateProgress(self, current):
        pass

    def pause(self):
        loader.Loadable.pause(self)
        self.Interface.pause()

    def unpause(self):
        loader.Loadable.unpause(self)
        self.Interface.unpause()

    def destroy(self):
        loader.Loadable.destroy(self)
        self.Interface.quit()


class CopyLoader(loader.Loadable, loader.FileManagerAware):
    '''
    very similar to ranger's own CopyLoader. Difference: FS ops are executed
    externally using ExternalLoader
    '''
    progressbar_supported = True
    def __init__(self, copy_buffer, do_cut=False, overwrite=False, sudo=False):
        self.copy_buffer = tuple(copy_buffer)
        self.do_cut = do_cut
        self.original_copy_buffer = copy_buffer
        self.original_path = self.fm.thistab.path
        self.overwrite = overwrite
        self.percent = 0
        if self.copy_buffer:
            self.one_file = self.copy_buffer[0]
        loader.Loadable.__init__(self, self.generate(), 'Calculating size...')

        self.Sudo = sudo
        self.SubLoader = None

    def generate(self):
        from ranger.ext import shutil_generatorized as shutil_g
        if not self.copy_buffer:
            return
        # TODO: Don't calculate size when renaming (needs detection)
        bytes_per_tick = shutil_g.BLOCK_SIZE
        self.SubLoader = ExternalLoader(0, self.Sudo, _CopyLoader_calculate_size,
                                        args=([f.path for f in self.copy_buffer], bytes_per_tick))
        for size in self.SubLoader.load_generator:
            yield
        if size == 0:
            size = 1
        bar_tick = 100.0 / (float(size) / bytes_per_tick)
        total = 0
        if self.do_cut:
            self.original_copy_buffer.clear()
            if len(self.copy_buffer) == 1:
                self.description = "moving: " + self.one_file.path
            else:
                self.description = "moving files from: " + self.one_file.dirname
            for f in self.copy_buffer:
                self.SubLoader = ExternalLoader(0, self.Sudo, _CopyLoader_deferred,
                                                args=(shutil_g.move,),
                                                kwargs={'args': (f.path, self.original_path),
                                                        'kwargs': {'overwrite': self.overwrite}})
                n = 0
                for n in self.SubLoader.load_generator:
                    self.percent = (total + n) * bar_tick
                    yield
                total += n
        else:
            if len(self.copy_buffer) == 1:
                self.description = "copying: " + self.one_file.path
            else:
                self.description = "copying files from: " + self.one_file.dirname
            for f in self.copy_buffer:
                if os.path.isdir(f.path):
                    self.SubLoader = ExternalLoader(0, self.Sudo, _CopyLoader_deferred,
                                                    args=(shutil_g.copytree,),
                                                    kwargs={'args': (f.path, os.path.join(self.original_path, f.basename)),
                                                            'kwargs': {'symlinks': True,
                                                                       'overwrite': self.overwrite}})
                    n = 0
                    for n in self.SubLoader.load_generator:
                        self.percent = (total + n) * bar_tick
                        yield
                    total += n
                else:
                    self.SubLoader = ExternalLoader(0, self.Sudo, _CopyLoader_deferred,
                                                    args=(shutil_g.copy2,),
                                                    kwargs={'args': (f.path, self.original_path),
                                                            'kwargs': {'symlinks': True,
                                                                       'overwrite': self.overwrite}})
                    n = 0
                    for n in self.SubLoader.load_generator:
                        self.percent = (total + n) * bar_tick
                        yield
                    total += n
        cwd = self.fm.get_directory(self.original_path)
        cwd.load_content()

    def pause(self):
        loader.Loadable.pause(self)
        if self.SubLoader is not None:
            self.SubLoader.pause()

    def unpause(self):
        loader.Loadable.unpause(self)
        if self.SubLoader is not None:
            self.SubLoader.unpause()

    def destroy(self):
        loader.Loadable.destroy(self)
        if self.SubLoader is not None:
            self.SubLoader.destroy()


def _CopyLoader_calculate_size(paths, bytes_per_tick):
    import os
    join = os.path.join

    def getSize(path, bytes_per_tick=bytes_per_tick):
        r = os.stat(path).st_size
        rest = r % bytes_per_tick
        if rest != 0:
            r += bytes_per_tick - rest
        return r

    size = 0
    for path in paths:
        if os.path.isdir(path):
            for base, ds, fs in os.walk(path):
                for f in fs:
                    size += getSize(join(base, f))
        else:
            size += getSize(path)

    return size


def deferred_count(gen, interval=0.033):
    prev = time.time()
    last = None
    i = None
    for i, x in enumerate(gen):
        now = time.time()
        if (now - prev) < interval:
            continue
        prev = now

        yield i
        last = i

    if i != last:
        yield i

def _CopyLoader_deferred(f, args=None, kwargs=None):
    for n in deferred_count(f(*([] if args is None else args),
                              **({} if kwargs is None else kwargs))):
        yield n



class paste(Command):
    '''
    Interface to CopyLoader
    '''
    def __init__(self, *args, **kwargs):
        Command.__init__(self, *args, **kwargs)

    def execute(self):
        flags, rest = self.parse_flags()

        global Sudo
        self.fm.loader.add(CopyLoader(
            self.fm.copy_buffer, do_cut=self.fm.do_cut, overwrite='o' in flags, sudo=Sudo,
        ))



class Mask(object):
    '''
    construct to enable external execution of other module's functions
    '''
    def __init__(self, module, name):
        self.Module = module
        self.Name = name

        self.F = getattr(module, name)

    def putOn(self):
        setattr(self.Module, self.Name, self)

    def putDown(self):
        setattr(self.Module, self.Name, self.F)

    def __call__(self, *args, **kwargs):
        self.putDown()

        global Sudo
        loader = ExternalLoader(None, Sudo, self.F, args, kwargs)
        for r in loader.load_generator:
            pass

        self.putOn()
        return r


class MaskedEnvironment(object):
    '''
    convenience environment for multiple masks
    '''
    def __init__(self, items):
        self.Items = items
        self._Masks = None

    def __enter__(self):
        self.Masks = [Mask(module, name) for module, name in self.Items]
        for m in self.Masks:
            m.putOn()

    def __exit__(self, type, value, traceback):
        for m in self.Masks:
            m.putDown()

def masked(f, items):
    def _f(*args, **kwargs):
        with MaskedEnvironment(items):
            return f(*args, **kwargs)
    return _f


class delete(commands.delete):
    def __init__(self, *args, **kwargs):
        commands.delete.__init__(self, *args, **kwargs)

    _Items = [(os, 'remove'), (shutil, 'rmtree')]
    execute = masked(commands.delete.execute, _Items)
    _question_callback = masked(commands.delete._question_callback, _Items)



class rename(commands.rename):
    def __init__(self, *args, **kwargs):
        commands.rename.__init__(self, *args, **kwargs)

    execute = masked(commands.rename.execute, [(os, 'renames')])


class mkdir(commands.mkdir):
    def __init__(self, *args, **kwargs):
        commands.mkdir.__init__(self, *args, **kwargs)

    execute = masked(commands.mkdir.execute, [(os, 'makedirs')])
