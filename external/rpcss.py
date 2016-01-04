'''
RPC Stream Secure
'''

import threading
import Queue

# import logging
# logging.getLogger().setLevel(logging.DEBUG)
# logFile = logging.FileHandler('/home/arappold/log')
# logFile.setFormatter(logging.Formatter('%(asctime)s %(process)d %(message)s'))
# logging.getLogger().addHandler(logFile)


def write(x, stream):
    '''
    writes '{len(x)}\n{x}'.
    '''
    if isinstance(x, unicode):
        x = x.encode()
    stream.write('{}\n'.format(len(x)))
    stream.write(x)
    stream.flush()


class EOS(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


def read(stream):
    '''
    reads '{len(x)}\n{x}' and returns x.

    raises EOS.
    '''
    n = stream.readline()
    if len(n) == 0:
        raise EOS
    n = int(n[:-1:])
    r = stream.read(n)
    return r


class Reader(threading.Thread):
    '''
    Thread.

    readF shall raise EOS.
    '''
    def __init__(self, readF, autostart=True):
        threading.Thread.__init__(self)

        self.ReadF = readF
        self.Autostart = autostart

        self.Queue = Queue.Queue()
        self.Stop = False
        self.Exception = None

        self.daemon = True

        if autostart:
            self.start()

    def run(self):
        try:
            while True:
                if self.Stop:
                    break

                x = self.ReadF()
                self.Queue.put(x)
        except EOS:
            pass
        except Exception, e:
            self.Exception = e
            raise

    def __del__(self):
        if self.isAlive():
            self.Stop = True
            self.join()


class IO(object):
    '''
    container for both input and output stream.

    uses functions read and write.
    '''
    def __init__(self, inStream, outStream):
        self.InStream = inStream
        self.OutStream = outStream

        self.InReader = inReader = Reader(self._read)
        self.InQueue = inReader.Queue

    def _read(self):
        return read(self.InStream)

    def write(self, x):
        write(x, self.OutStream)


AES_MAX_BYTES = 2^20 # 1MB

class EncryptedIO(IO):
    AES = None
    Struct = None

    '''
    uses RSA (init) and AES (read/write) encryption.
    '''
    def __init__(self, inStream, outStream):
        IO.__init__(self, inStream, outStream)

        import Crypto.PublicKey.RSA as rsa
        import Crypto.Cipher.PKCS1_OAEP as pkcs1_oaep
        import Crypto.Random as rand

        if EncryptedIO.AES is None:
            import Crypto.Cipher.AES as aes
            EncryptedIO.AES = aes
            import struct
            EncryptedIO.Struct = struct

        self._random = rand.new()
        self._readCipher = None
        self._writeCipher = None
        self._readByteCount = 2*AES_MAX_BYTES
        self._writeByteCount = 2*AES_MAX_BYTES
        self._nextReadRefresh = 0
        self._nextWriteRefresh = 0

        # exchange public RSA keys
        privateKey = rsa.generate(2048)
        self._readCipher = pkcs1_oaep.new(privateKey)

        publicKey = privateKey.publickey().exportKey()
        IO.write(self, publicKey)

        publicKey = self.InQueue.get()
        publicKey = rsa.importKey(publicKey)
        self._writeCipher = pkcs1_oaep.new(publicKey)

    def _read(self):
        '''
        plain read.
        only called once.
        '''
        ## eliminate race condition
        while not hasattr(self, 'InReader'):
            pass
        self.InReader.ReadF = self._read_encrypted
        return IO._read(self)

    def _read_encrypted(self):
        '''
        see self.write
        '''
        y = IO._read(self)

        if self._nextReadRefresh < self._readByteCount:
            # a)
            keyIv = self._readCipher.decrypt(y)
            key, iv = keyIv[:16:], keyIv[16::]
            self._readCipher = EncryptedIO.AES.new(key, EncryptedIO.AES.MODE_CFB, iv)

            # b)
            y = IO._read(self)
            t = self._readCipher.decrypt(y)

            self._readByteCount = 0
            self._nextReadRefresh = EncryptedIO.Struct.unpack('Q', t)[0] % AES_MAX_BYTES

            return self._read_encrypted()

        r = self._readCipher.decrypt(y)
        self._readByteCount += len(r)
        return r

    def write(self, x):
        '''
        see self._read_encrypted
        '''
        if self._nextWriteRefresh < self._writeByteCount:
            # a)
            key = self._random.read(16)
            iv = self._random.read(EncryptedIO.AES.block_size)

            y = self._writeCipher.encrypt(key + iv)
            IO.write(self, y)

            self._writeCipher = EncryptedIO.AES.new(key, EncryptedIO.AES.MODE_CFB, iv)

            # b)
            t = self._random.read(8)
            y = self._writeCipher.encrypt(t)
            IO.write(self, y)

            self._writeByteCount = 0
            self._nextWriteRefresh = EncryptedIO.Struct.unpack('Q', t)[0] % AES_MAX_BYTES

        self._writeByteCount += len(x)
        y = self._writeCipher.encrypt(x)
        IO.write(self, y)


class T(object):
    '''
    tag/token
    '''
    def __init__(self, id):
        self.Id = id

    def __eq__(self, other):
        if not isT(other):
            return False
        return self.Id == other.Id

    def __hash__(self):
        return hash(self.Id)

    def __repr__(self):
        return 'T({})'.format(repr(self.Id))

def isT(x):
    ## type(x) == T fails due to pickling/unpickling
    return type(x).__name__ == 'T'

Tpass = T('pass')
Tinterval = T('interval')
Ttimeout = T('timeout')
Tpause = T('pause')
Tcall = T('call')
Tcall_iter = T('call_iter')
Tend = T('end')
Tcall_step = T('call_step')
Tnext = T('next')
Texception = T('exception')
Tstop = T('stop')


class _RpcBase(object):
    Pickle = None

    def __init__(self, io):
        self.IO = io

        self._InQueue = io.InQueue

        if _RpcBase.Pickle is None:
            import pickle
            import savestate
            _RpcBase.Pickle = pickle

    def _read(self, block=True, timeout=None):
        while True:
            r = self._readWithPass(block=block, timeout=timeout)
            if r == Tpass:
                continue
            return r

    def _readWithPass(self, block=True, timeout=None):
        r = self._InQueue.get(block=block, timeout=timeout)
        return _RpcBase.Pickle.loads(r)

    def _write(self, x):
        x = _RpcBase.Pickle.dumps(x, protocol=2)
        self.IO.write(x)

    def pass_(self):
        '''
        does nothing.

        fails if the connection is down.
        '''
        self._write(Tpass)


class RpcServer(_RpcBase):
    def __init__(self, io):
        _RpcBase.__init__(self, io)

    def setInterval(self, interval):
        '''
        see RpcClient.
        '''
        self._write(Tinterval)
        self._write(interval)

    def setTimeout(self, timeout):
        '''
        see RpcClient.
        '''
        self._write(Ttimeout)
        self._write(timeout)

    def setPause(self, value):
        '''
        see RpcClient.
        '''
        self._write(Tpause)
        self._write(value)

    def call(self, f, args=tuple(), kwargs=dict()):
        self._write(Tcall)
        self._write( (f, args, kwargs) )

        r = self._read()
        if r == Texception:
            raise self._read()

        return r

    def call_iter(self, f, args=tuple(), kwargs=dict()):
        '''
        yields items that f(*args, **kwargs) yields.

        remote produces items continously.
        see self.setPause.
        '''
        self._write(Tcall_iter)
        self._write( (f, args, kwargs) )

        while True:
            n = self._read()
            if isT(n):
                if n == Tend:
                    break

                if n == Texception:
                    raise self._read()

            yield n

    def hasInput(self):
        '''
        for non-blocking use of call_iter.
        '''
        return not self._InQueue.empty()

    def call_step(self, f, args=tuple(), kwargs=dict()):
        '''
        yields items that f(*args, **kwargs) yields.

        remote produces items stepwise on next.
        '''
        self._write(Tcall_step)
        self._write( (f, args, kwargs) )

        init = self._read()
        if init == Texception:
            raise self._read()

        while True:
            self._write(Tnext)

            n = self._read()
            if isT(n):
                if n == Tend:
                    break

                if n == Texception:
                    raise self._read()

            yield n

    def addToPath(self, x):
        '''
        adds path or sequence of paths to the remote sys.path.
        '''
        import os

        if isinstance(x, basestring):
            items = [x]
        else:
            items = iter(x)

        items = [os.path.abspath(item) for item in items]

        def _addToPath(items):
            import sys

            path = sys.path
            for item in items:
                if item not in path:
                    path.append(item)

        self.call(_addToPath, (items,))

    def removeFromPath(self, x):
        '''
        removes path or sequence of paths from the remote sys.path.
        '''
        import os

        if isinstance(x, basestring):
            items = [x]
        else:
            items = iter(x)

        items = [os.path.abspath(item) for item in items]

        def _removeFromPath(x):
            import sys

            path = sys.path
            for item in items:
                if item in path:
                    path.remove(item)

        self.call(_removeFromPath, (items,))

    def chdir(self, to):
        def _chdir(to):
            import os
            os.chdir(to)

        self.call(_chdir, (to,))

    def stop(self):
        # raise Exception('stop')
        self._write(Tstop)


class RpcClient(_RpcBase, threading.Thread):
    def __init__(self, io, interval=0.33, timeout=60, autostart=True):
        _RpcBase.__init__(self, io)
        threading.Thread.__init__(self)

        self.Interval = interval
        self.Timeout = timeout
        self.Autostart = autostart

        self.Pause = False
        self.Stop = False
        self.Exception = None

        self.StepGen = None

        self.daemon = True

        if autostart:
            self.start()

    _Runs = {}

    def run(self):
        import time

        i = 0
        while True:
            if self.Stop:
                break

            try:
                t = self._readWithPass(block=True, timeout=self.Interval)
            except Queue.Empty:
                if (self.Timeout / self.Interval) < i and self.StepGen is None:
                    break

                i += 1
                continue
            except Exception, e:
                self.Exception = e
                raise

            i = 0
            try:
                RpcClient._Runs[t](self)
            except Exception, e:
                self.Exception = e
                raise

    def _run_pass(self):
        pass
    _Runs[Tpass] = _run_pass

    def _run_setInterval(self):
        self.Interval = self._read()
    _Runs[Tinterval] = _run_setInterval

    def _run_setTimeout(self):
        self.Timeout = self._read()
    _Runs[Ttimeout] = _run_setTimeout

    def _run_setPause(self):
        self.Pause = self._read()
    _Runs[Tpause] = _run_setPause

    def _run_call(self):
        data = self._read()
        f, args, kwargs = data

        try:
            r = f(*args, **kwargs)
        except Exception:
            self._write_exception()
            return

        self._write(r)
    _Runs[Tcall] = _run_call

    def _run_call_iter(self):
        data = self._read()
        f, args, kwargs = data

        try:
            r = f(*args, **kwargs)
        except Exception:
            self._write_exception()
            return

        while True:
            self._call_iter_handleInput()

            if self.Stop:
                return

            if self.Pause:
                continue

            try:
                n = next(r)
            except StopIteration:
                break
            except Exception:
                self._write_exception()
                return

            self._write(n)

        self._write(Tend)
    _Runs[Tcall_iter] = _run_call_iter

    def _call_iter_handleInput(self):
        while True:
            try:
                t = self._read(block=True, timeout=self.Interval if self.Pause else 0)
            except Queue.Empty:
                return

            if not (t == Tpause or t == Tstop):
                raise Exception('recieved unexpected token {}'.format(t))

            RpcClient._Runs[t](self)

    def _run_call_step(self):
        data = self._read()
        f, args, kwargs = data

        try:
            r = f(*args, **kwargs)
        except Exception:
            self._write_exception()
            return

        self.StepGen = r
        self._write(Tnext) # init
    _Runs[Tcall_step] = _run_call_step

    def _run_next(self):
        try:
            n = next(self.StepGen)
        except StopIteration:
            n = Tend
        except Exception:
            self._write_exception()
            self.StepGen = None
            return

        self._write(n)
    _Runs[Tnext] = _run_next

    def _run_stop(self):
        self.Stop = True
    _Runs[Tstop] = _run_stop

    def _write_exception(self):
        import traceback
        self._write(Texception)
        self._write(Exception(traceback.format_exc()))

    def __del__(self):
        if self.isAlive():
            self.Stop = True
            self.join()




if __name__ == '__main__':
    #import sys

    #io = RpcClient(EncryptedIO(sys.stdin, sys.stdout))
    #io.join()

    if False:
        import sys
        import subprocess as sub

        cl = EncryptedIO

        if '-child' in sys.argv:
            Parent = False

            io = cl(sys.stdin, sys.stdout)

            io.write(io.InQueue.get())
            io.write('Message from child to parent')

            exit()

        else:
            Parent = True

            p = sub.Popen([sys.executable, __file__, '-child'], stdin=sub.PIPE, stdout=sub.PIPE)
            io = cl(p.stdout, p.stdin)

            io.write('Message from parent to child')

            print io.InQueue.get()
            print io.InQueue.get()

            exit()


    if True:
        import sys
        import subprocess as sub
        import time

        cl = EncryptedIO

        if '-child' in sys.argv:
            Parent = False

            io = cl(sys.stdin, sys.stdout)

            client = RpcClient(io)
            client.join()

            exit()

        else:
            Parent = True

            p = sub.Popen([sys.executable, __file__, '-child'], stdin=sub.PIPE, stdout=sub.PIPE)
            io = cl(p.stdout, p.stdin)

            server = RpcServer(io)

            def f():
                import sys
                import os

                return {'path': sys.path, 'ls': os.listdir('.')}

            from pprint import pprint
            pprint(server.call(f))

            server.addToPath('..')
            server.chdir('..')

            server.setInterval(1e-9)
            server.setTimeout(5)
            time.sleep(4)

            def f():
                import sys

                yield '> path'
                for path in sys.path:
                    yield path

            for i in server.call_iter(f):
                print i

            def f():
                import os

                yield '> ls'
                for name in os.listdir('.'):
                    yield name

            for i in server.call_step(f):
                print i

            server.setInterval(0.03)

            server.stop()

            exit()


