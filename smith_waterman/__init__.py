# -*- coding: utf-8 -*-

import ranger.api.commands as commands


## import ssw or sw
try:
    from . import ssw
    sw = None
except ImportError:
    ssw = None
    from . import sw


class CaseSensitiveStr(str):
    '''
    workaround for str.upper behaviour of swalign.
    '''
    def __init__(self, x):
        str.__init__(self, x)

    def upper(self):
        return self


## define sort key

class KeyBase(object):
    def __init__(self, ref, match, mismatch, gap_open, gap_extend):
        self.Ref = None
        self.Match = match
        self.Mismatch = mismatch
        self.GapOpen = gap_open
        self.GapExtend = gap_extend

        self.setRef(ref)

    def setRef(self, x):
        raise NotImplementedError

    def __call__(self, item):
        raise NotImplementedError


class SswKey(KeyBase):
    '''
    uses ssw (Complete-Striped-Smith-Waterman-Library).
    '''
    def __init__(self, ref='', match=2, mismatch=-1, gap_open=-2, gap_extend=0):
        self.Aligner = ssw.TextAligner(match=match, mismatch=-mismatch, gap_open=-gap_open, gap_extend=-gap_extend)

        KeyBase.__init__(self, ref, match, mismatch, gap_open, gap_extend)

    def setRef(self, x):
        self.Ref = x
        self.Aligner.set_ref(x)

    def __call__(self, item):
        r = self.Aligner.align(item)
        return r.score + float(r.ref_end - r.ref_begin + 1) / len(item)

class SwKey(KeyBase):
    '''
    uses sw (swalign).
    '''
    def __init__(self, ref='', match=2, mismatch=-1, gap_open=-2, gap_extend=0):
        scoring = sw.IdentityScoringMatrix(match, mismatch)
        self.Alignment = sw.LocalAlignment(scoring, gap_penalty=gap_open, gap_extension_penalty=gap_extend)

        KeyBase.__init__(self, ref, match, mismatch, gap_open, gap_extend)

    def setRef(self, x):
        self.Ref = CaseSensitiveStr(x)

    def __call__(self, item):
        r = self.Alignment.align(self.Ref, CaseSensitiveStr(item))
        return r.score + float(r.r_end - r.r_pos) / len(item)


class SplitTransformKey(object):
    '''
    splits ref and applies transformation to items.

    calls key for every sub ref and returns sum.
    '''
    def __init__(self, key, splitBy=None, transF=lambda item: item):
        self.Key = key
        self.SplitBy = splitBy
        self.TransF = transF

        self._Refs = []

    def setRef(self, x):
        self._Refs = x.split(self.SplitBy)

    def __call__(self, item):
        item = self.TransF(item)
        r = 0

        for ref in self._Refs:
            self.Key.setRef(ref)
            r += self.Key(item)

        return r


if ssw is not None:
    key = SswKey()
else:
    key = SwKey()

GlobalSwKey = SplitTransformKey(key, None, lambda item: item.relative_path)

# add to directory sort
import ranger.container.directory as directory
directory.Directory.sort_dict['smith waterman'] = GlobalSwKey


class sw_nav(commands.Command):
    SortSettings = None

    OPEN_ON_ENTER = 'e'
    IGNORE_CASE   = 'i'
    KEEP_OPEN     = 'k'
    SMART_CASE    = 's'
    OPEN_ON_TAB   = 't'

    def __init__(self, *args, **kwargs):
        commands.Command.__init__(self, *args, **kwargs)

        flags, ref = self.parse_flags()
        self.Flags = flags
        self.Ref = ref

    def quick(self):
        if sw_nav.SortSettings is None: # init
            settings = self.fm.settings
            sw_nav.SortSettings = {name: getattr(settings, name) for name in ['sort', 'sort_reverse', 'sort_directories_first']}

            settings.sort = 'smith waterman'
            settings.sort_reverse = True
            settings.sort_directories_first = False

        ignoreCase = sw_nav.IGNORE_CASE in self.Flags or (sw_nav.SMART_CASE in self.Flags and self.Ref.islower())

        # modify global key
        if ignoreCase:
            GlobalSwKey.setRef(self.Ref.lower())
            GlobalSwKey.TransF = lambda item: item.relative_path_lower
        else:
            GlobalSwKey.setRef(self.Ref)
            GlobalSwKey.TransF = lambda item: item.relative_path

        # force sort
        thisdir = self.fm.thisdir
        thisdir.sort()
        thisdir.move(to=0)

        return False

    def tab(self, tabnum):
        if sw_nav.OPEN_ON_TAB in self.Flags:
            self._open()
            self.cancel()
            return

        self.fm.thisdir.move(down=tabnum)

    def execute(self):
        if sw_nav.OPEN_ON_ENTER in self.Flags:
            self._open()
            self.cancel()

    def _open(self):
        self.fm.move(right=1)

        if sw_nav.KEEP_OPEN in self.Flags:
            if len(self.Ref) == 0:
                line = self.line
            else:
                line = self.line[:-len(self.Ref):]
            self.fm.open_console(line)

    def cancel(self):
        if sw_nav.SortSettings is not None:
            settings = self.fm.settings
            for name, value in sw_nav.SortSettings.iteritems():
                setattr(settings, name, value)
            sw_nav.SortSettings = None


