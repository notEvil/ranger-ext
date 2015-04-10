import os
import sys
import threading
import collections
import re
import pickle, savestate
import time
import subprocess as sub


def send(x, stream, forceBin=False):
    if forceBin or not isinstance(x, basestring):
        x = pickle.dumps(x, -1)
        stream.write( '\0{}\n'.format(len(x)) )
    stream.write(x)
    stream.flush()

def recieve(stream, pattern=re.compile('\0(\d+)\n')):
    '''
    returns x, isObj
    or None if EOS
    '''
    n = stream.readline()
    if len(n) == 0:
        return None
    match = pattern.match(n)
    if match is not None:
        n = int(match.group(1))
        n = stream.read(n)
        n = pickle.loads(n)
        return n, True
    return n, False


class StreamReader(threading.Thread):
    def __init__(self, stream, callback=lambda x, isObj: False):
        threading.Thread.__init__(self)

        self.Stream = stream
        self.Callback = callback
        self.Stop = False
        self.Queue = collections.deque()

        self.daemon = True

    def __enter__(self):
        self.Stop = False
        self.start()
        return self

    def run(self):
        while True:
            if self.Stop:
                break

            n = recieve(self.Stream)
            if n is None:
                break

            x, isObj = n
            if not self.Callback(x, isObj):
                self.Queue.append(n)

    def __exit__(self, type, value, traceback):
        self.Stop = True
        self.join()





def runExternal(interface, f, args, kwargs):
    '''
    prints messages to stdout/stderr
    yields objects
    '''
    interface.f = f
    interface.args = args
    interface.kwargs = kwargs
    onStdout = interface.OnStdout
    onStderr = interface.OnStderr
    interface.OnStdout = interface.OnStderr = lambda x, isObj: False
    interface._start()
    yield None # init

    stdoutQueue = interface._stdout.Queue
    stderrQueue = interface._stderr.Queue
    while True:
        if not interface.isAlive():
            break

        while len(stderrQueue) != 0:
            x, isObj = stderrQueue.popleft()
            if isObj:
                raise x
            print >> sys.stderr, x,

        nothing = True
        while len(stdoutQueue) != 0:
            x, isObj = stdoutQueue.popleft()
            if not isObj:
                print x,
                continue
            yield x
            nothing = False

        if nothing:
            yield None

    while len(stderrQueue) != 0:
        x, isObj = stderrQueue.popleft()
        if isObj:
            raise x
        print >> sys.stderr, x,

    while len(stdoutQueue) != 0:
        x, isObj = stdoutQueue.popleft()
        if not isObj:
            print x,
            continue
        yield x

    interface.OnStdout = onStdout
    interface.OnStderr = onStderr


class Interface(object):
    def __init__(self, sudo=False, beforeSudo=lambda: None,
                       onStdout=None, onStderr=None,
                       popenArgs=None, importPaths=None):
        self.Sudo = sudo
        self.BeforeSudo = beforeSudo
        self.OnStdout = self._onStdout if onStdout is None else onStdout
        self.OnStderr = self._onStderr if onStderr is None else onStderr
        self.PopenArgs = {} if popenArgs is None else popenArgs
        self.ImportPaths = [] if importPaths is None else importPaths

        self._f = None
        self._args = None
        self._kwargs = None

        self._popen = None
        self._stdout = None
        self._stderr = None


    def _start(self):
        if self.isAlive():
            raise Exception('Interface is still in use')

        cmds = []
        if self.Sudo:
            self.BeforeSudo()
            cmds.append('sudo')
        import __main__
        cmds.extend([sys.executable, __file__])
        cmds.extend(self.ImportPaths)
        popenArgs = self.PopenArgs.copy()
        popenArgs['stdin'] = popenArgs['stdout'] = popenArgs['stderr'] = sub.PIPE
        self._popen = sub.Popen(cmds, **popenArgs)

        if self._stdout is not None:
            self._stdout.Stop = True
        self._stdout = StreamReader(self._popen.stdout, callback=self.OnStdout)
        self._stdout.start()

        if self._stderr is not None:
            self._stderr.Stop = True
        self._stderr = StreamReader(self._popen.stderr, callback=self.OnStderr)
        self._stderr.start()

        send((self.f, self.args, self.kwargs), self._popen.stdin)

    def _onStdout(self, x, isObj):
        if isObj:
            return False
        print x,
        return True

    def _onStderr(self, x, isObj):
        if isObj:
            return False
        print >> sys.stderr, x,
        return True

    def isAlive(self):
        if self._popen is None:
            return False
        return self._popen.poll() is None

    def pause(self):
        if not self.isAlive():
            return
        send('pause\n', self._popen.stdin)

    def unpause(self):
        if not self.isAlive():
            return
        send('unpause\n', self._popen.stdin)

    def quit(self):
        if not self.isAlive():
            return
        send('quit\n', self._popen.stdin)





if __name__ == '__main__':
    import time

    for path in sys.argv[1::]:
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        if path not in sys.path:
            sys.path.append(path)

    reader = None

    try:
        reader = StreamReader(sys.stdin)
        reader.start()

        while len(reader.Queue) == 0:
            time.sleep(0.033)

        f, args, kwargs = reader.Queue.popleft()[0]
        r = f(*args, **kwargs)

        if type(r).__name__ == 'generator':
            pause = False
            quit = False

            while True:
                while len(reader.Queue) != 0:
                    x, isObj = reader.Queue.popleft()
                    if x == 'pause\n':
                        pause = True
                    elif x == 'unpause\n':
                        pause = False
                    elif x == 'quit\n':
                        quit = True
                        break

                if quit:
                    break

                if pause:
                    time.sleep(0.1)
                    continue

                try: rr = next(r)
                except StopIteration: break

                send(rr, sys.stdout)
        else:
            send(r, sys.stdout)

    except Exception, e:
        #import traceback
        #send(traceback.format_exc(), sys.stderr)
        send(e, sys.stderr)
    finally:
        if reader is not None:
            reader.Stop = True
            #reader.join()


