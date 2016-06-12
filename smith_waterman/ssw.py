'''
straightforward wrapper for ssw_lib
'''

import os
import sys

path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Complete-Striped-Smith-Waterman-Library', 'src'))
append = path not in sys.path
if append:
    sys.path.append(path)
import ssw_lib
if append:
    sys.path.pop()

import ctypes as ct

class falseStr(str): # ssw_lib does some weird check
    def __nonzero__(self):
        return False

ssw = ssw_lib.CSsw( falseStr(path) )

def toInt(query, ref):
    chars = set(query) | set(ref)
    if 100 < len(chars):
        raise Exception('number of different characters shall not exceed 100')
    map = {c: i for i, c in enumerate(chars)} # char: int
    rQuery = [map[c] for c in query]
    rQuery = (ct.c_int8 * len(rQuery))(*rQuery)
    rRef = [map[c] for c in ref]
    rRef = (ct.c_int8 * len(rRef))(*rRef)
    return rQuery, rRef, map

def score(query, ref, match=2, mismatch=-1, gap_open=-2, gap_extend=0):
    iQuery, iRef, cMap = toInt(query, ref)

    n = len(cMap)
    subMat = (ct.c_int8 * n**2)()
    subMat[::] = [mismatch]*len(subMat)
    subMat[::(n + 1)] = [match]*n

    try:
        qProfile = ssw.ssw_init(iQuery, len(query), subMat, n, 2)
        rr = ssw.ssw_align(qProfile, iRef, len(ref), -gap_open, -gap_extend, 0, 0, 0, 15)

        r = rr.contents.nScore
    except:
        raise
    finally:
        try: ssw.align_destroy(rr)
        except: pass

        try: ssw.init_destroy(qProfile)
        except: pass

    return r

