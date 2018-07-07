# -*- coding: utf-8 -*-

import ranger.api.commands as commands
import parasail


class SwSortKey:
    def __init__(self):
        self._Alphabet = set()
        self._MatchScore = 2
        self._MismatchScore = -1
        self._GapOpenScore = -2
        self._GapExtendScore = 0
        self._MatchScoreMatrix = None

        self._ReferenceString = None

    def set_reference_string(self, referenceString):
        self._update_alphabet(referenceString)
        self._ReferenceString = referenceString

    def __call__(self, string):
        self._update_alphabet(string)

        r = parasail.sw_striped_16(
            string,
            self._ReferenceString,
            -self._GapOpenScore,
            -self._GapExtendScore,
            self._MatchScoreMatrix,
        )

        r = r.score + 1 / len(string)
        return r

    def _update_alphabet(self, x):
        originalLength = len(self._Alphabet)

        self._Alphabet.update(x)

        if len(self._Alphabet) == originalLength:
            return

        self._MatchScoreMatrix = parasail.matrix_create(''.join(self._Alphabet), self._MatchScore, self._MismatchScore)


class SwSplitApplySortKey(SwSortKey):
    def __init__(self, splitBy=None, applyF=lambda item: item):
        '''
        - splits reference string by splitBy
        - applies applyF to sort key
        - matches new sort key to all parts of reference string
        - returns sum of scores
        '''
        super().__init__()

        self.SplitBy = splitBy
        self.ApplyF = applyF

        self._ReferenceStrings = None

    def set_reference_string(self, referenceString):
        referenceStrings = referenceString.split(self.SplitBy)

        for refString in referenceStrings:
            self._update_alphabet(refString)

        self._ReferenceString = referenceString
        self._ReferenceStrings = referenceStrings

    def __call__(self, x):
        originalReferenceString = self._ReferenceString

        x = self.ApplyF(x)
        r = 0

        try:
            for referenceString in self._ReferenceStrings:
                self._ReferenceString = referenceString
                r += super().__call__(x)

        finally:
            self._ReferenceString = originalReferenceString

        return r


sortKey = SwSplitApplySortKey()


class sw_nav(commands.Command):
    OPEN_ON_ENTER = 'e'
    IGNORE_CASE = 'i'
    KEEP_OPEN = 'k'
    SMART_CASE = 's'
    OPEN_ON_TAB = 't'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._Flags, self._ReferenceString = self.parse_flags()

    def quick(self):
        global sortKey

        ignoreCase = self.IGNORE_CASE in self._Flags or (self.SMART_CASE in self._Flags
                                                         and self._ReferenceString.islower())

        # modify global key
        if ignoreCase:
            sortKey.set_reference_string(self._ReferenceString.lower())
            sortKey.ApplyF = lambda item: item.relative_path_lower

        else:
            sortKey.set_reference_string(self._ReferenceString)
            sortKey.ApplyF = lambda item: item.relative_path

        # force sort
        thisdir = self.fm.thisdir
        if thisdir.files_all is None:
            return False

        thisdir.files_all.sort(key=sortKey, reverse=True)
        thisdir.refilter()
        thisdir.move(to=0)

        return False

    def tab(self, tabnum):
        if self.OPEN_ON_TAB in self._Flags:
            self._finish()
            self._open()
            return

        self.fm.thisdir.move(down=tabnum)

    def execute(self):
        if self.OPEN_ON_ENTER not in self._Flags:
            return

        self._finish()
        self._open()

    def _open(self):
        self.fm.move(right=1)

        if self.KEEP_OPEN not in self._Flags:
            return

        line = self.line if len(self._ReferenceString) == 0 else self.line[:-len(self._ReferenceString):]

        self.fm.open_console(line)

    def cancel(self):
        self._finish()

    def _finish(self):
        thisdir = self.fm.thisdir
        thisdir.sort()
