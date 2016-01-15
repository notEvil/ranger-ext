'''
looks for ssw_wrap and libssw.so.

dirty imports ssw_wrap and loads libssw.so.

enables charset based use of libssw via dirty sub class `TextAligner`.
relies heavily on implementation details of super class `ssw.Aligner`.
'''

import os
import sys
import ctypes


## import ssw_wrap

# find module/library path
path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Complete-Striped-Smith-Waterman-Library', 'src'))

if not os.path.exists(path):
    raise ImportError('Complete-Striped-Smith-Waterman-Library/src does not exist. Run setup_ssw.sh')

# replace ctypes.cdll.LoadLibrary
_LoadLibrary = ctypes.cdll.LoadLibrary
def LoadLibrary(name):
    return _LoadLibrary(os.path.join(path, name))

ctypes.cdll.LoadLibrary = LoadLibrary

# add path to sys.path
add = path not in sys.path

if add:
    sys.path.append(path)

# import
import ssw_wrap as ssw

# undo
if add:
    sys.path.pop()

ctypes.cdll.LoadLibrary = _LoadLibrary



class DefaultGetter(object):
    '''
    helper.
    '''
    def __init__(self, d, default):
        self.D = d
        self.Default = default

    def __getitem__(self, x):
        return self.D.get(x, self.Default)


class TextAligner(ssw.Aligner):
    def __init__(self, ref_seq='', match=2, mismatch=2, gap_open=3, gap_extend=1, report_secondary=False, report_cigar=False, charset='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'):
        # define charset
        self.Charset = charset

        self._Charset = set(charset)

        # redefine self.base_to_int, self.int_to_base
        b2i = {c: i + 1 for i, c in enumerate(charset)}
        self.base_to_int = DefaultGetter(b2i, 0)
        self.int_to_base = DefaultGetter({v: k for k, v in b2i.iteritems()}, '?')

        # call super init
        ssw.Aligner.__init__(self, ref_seq=ref_seq, match=match, mismatch=mismatch, gap_open=gap_open, gap_extend=gap_extend, report_secondary=report_secondary, report_cigar=report_cigar)


    # redefine self.set_mat
    def set_mat(self, match=2, mismatch=2):
        # call super set_mat
        ssw.Aligner.set_mat(self, match=match, mismatch=mismatch)

        # create different self.mat
        n = len(self._Charset)
        mat_decl = ctypes.c_int8 * (n + 1)**2

        m = [-mismatch] * (n + 1)**2
        for i in xrange(n + 1):
            m[i*(n + 1) + i] = match # diagonal
            m[i*(n + 1)] = 0 # first row
            m[i] = 0 # first column

        self.mat = mat_decl(*m)


    # redefine self.ssw_init
    def ssw_init(self, read, readLen, mat, n, score_size):
        n = len(self._Charset)
        return TextAligner.libssw.ssw_init(read, readLen, mat, n + 1, score_size)


if __name__ == '__main__':
    # ref = 'AGCT'
    # query = 'GC'
    # charset = 'AGCT'

    ref = 'this is some reference text'
    query = 'this is some query text'
    charset = 'abcdefghijklmnopqrstuvwxyz'

    aligner = TextAligner(ref, match=2, mismatch=1, gap_open=2, gap_extend=0, charset=charset)
    res = aligner.align(query)

    print '>'
    print repr(res)
    print ref[res.ref_begin:res.ref_end + 1:]
    print query[res.query_begin:res.query_end + 1:]

