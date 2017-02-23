# -*- coding: utf-8 -*-

import ranger.api.commands as commands
from . import parasail


class SwSortKey:
    def __init__(self):
        self.Alphabet = set()
        self.MatchScore = 2
        self.MismatchScore = -1
        self.GapOpen = 2
        self.GapExtend = 0
        self.MatchMatrix = None

        self.Ref = None

    def setRef(self, ref):
        self.Ref = ref
        self._addToAlphabet(ref)

    def __call__(self, s):
        self._addToAlphabet(s)
        r = parasail.sw_striped_16(s, self.Ref, self.GapOpen, self.GapExtend, self.MatchMatrix)
        return r.score

    def _addToAlphabet(self, x):
        chars = set(x)
        newChars = chars - self.Alphabet
        if len(newChars) == 0:
            return

        self.Alphabet.update(newChars)
        self.MatchMatrix = parasail.matrix_create(''.join(self.Alphabet), self.MatchScore, self.MismatchScore)


class SwSplitApplySortKey(SwSortKey):
    '''
    - splits ref by splitBy
    - applies applyF to sort item
    - matches new sort item to all parts of ref
    - returns sum of scores
    '''
    def __init__(self, splitBy=None, applyF=lambda item: item):
        super().__init__()

        self.SplitBy = splitBy
        self.ApplyF = applyF

        self._Refs = None

    def setRef(self, ref):
        self.Ref = ref
        self._Refs = refs = ref.split(self.SplitBy)
        for ref in refs:
            self._addToAlphabet(ref)

    def __call__(self, x):
        refBak = self.Ref

        x = self.ApplyF(x)
        r = 0

        try:
            for ref in self._Refs:
                self.Ref = ref
                r += super().__call__(x)
        finally:
            self.Ref = refBak

        return r


sortKey = SwSplitApplySortKey()


class sw_nav(commands.Command):
    OPEN_ON_ENTER = 'e'
    IGNORE_CASE   = 'i'
    KEEP_OPEN     = 'k'
    SMART_CASE    = 's'
    OPEN_ON_TAB   = 't'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.Flags, self.Ref = self.parse_flags()

    def quick(self):
        ignoreCase = sw_nav.IGNORE_CASE in self.Flags or (sw_nav.SMART_CASE in self.Flags and self.Ref.islower())

        # modify global key
        if ignoreCase:
            sortKey.setRef(self.Ref.lower())
            sortKey.ApplyF = lambda item: item.relative_path_lower
        else:
            sortKey.setRef(self.Ref)
            sortKey.ApplyF = lambda item: item.relative_path

        # force sort
        thisdir = self.fm.thisdir
        thisdir.files_all.sort(key=sortKey, reverse=True)
        thisdir.refilter()
        thisdir.move(to=0)

        return False

    def tab(self, tabnum):
        if sw_nav.OPEN_ON_TAB in self.Flags:
            self._finish()
            self._open()
            return

        self.fm.thisdir.move(down=tabnum)

    def execute(self):
        if sw_nav.OPEN_ON_ENTER not in self.Flags:
            return

        self._finish()
        self._open()

    def _open(self):
        self.fm.move(right=1)

        if sw_nav.KEEP_OPEN not in self.Flags:
            return

        if len(self.Ref) == 0:
            line = self.line
        else:
            line = self.line[:-len(self.Ref):]
        self.fm.open_console(line)

    def cancel(self):
        self._finish()

    def _finish(self):
        thisdir = self.fm.thisdir
        thisdir.sort()

