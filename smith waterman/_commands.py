# -*- coding: utf-8 -*-

from ranger.api.commands import *


import sys
import os
import re


# load swalign
path = os.path.abspath(os.path.dirname(__file__))
add = path not in sys.path

if add:
    sys.path.append(path)

import swalign as sw

if add:
    sys.path.pop()


class SmithWaterman(object):
    def __init__(self, pattern, transF=lambda item: item, match=2, mismatch=-1, gap_penalty=-2, gap_extension_penalty=0):
        self.Pattern = pattern
        self.TransF = transF

        scoring = sw.IdentityScoringMatrix(match, mismatch)
        self.Sw = sw.LocalAlignment(scoring, gap_penalty=gap_penalty, gap_extension_penalty=gap_extension_penalty)

    def __call__(self, item):
        item = self.TransF(item)
        align = self.Sw.align(item, self.Pattern)
        return align.score + float(align.r_end - align.r_pos) / len(item)

# add to directory sort
import ranger.container.directory as directory
GlobalSmithWaterman = SmithWaterman('', transF=lambda item: item.basename)
directory.Directory.sort_dict['smith waterman'] = GlobalSmithWaterman


class scout(Command):
    """:scout [-FLAGS] <pattern>

    Swiss army knife command for searching, traveling and filtering files.
    The command takes various flags as arguments which can be used to
    influence its behaviour:

    -a = automatically open a file on unambiguous match
    -e = open the selected file when pressing enter
    -f = filter files that match the current search pattern
    -g = interpret pattern as a glob pattern
    -i = ignore the letter case of the files
    -k = keep the console open when changing a directory with the command
    -l = letter skipping; e.g. allow "rdme" to match the file "readme"
    -m = mark the matching files after pressing enter
    -M = unmark the matching files after pressing enter
    -p = permanent filter: hide non-matching files after pressing enter
    -s = smart case; like -i unless pattern contains upper case letters
    -t = apply filter and search pattern as you type
    -v = inverts the match
    -w = compute smith waterman score and force apply ordering (decreasing)
         force pointer to first (best score) on pattern update

    Multiple flags can be combined.  For example, ":scout -gpt" would create
    a :filter-like command using globbing.
    """
    AUTO_OPEN       = 'a'
    OPEN_ON_ENTER   = 'e'
    FILTER          = 'f'
    SM_GLOB         = 'g'
    IGNORE_CASE     = 'i'
    KEEP_OPEN       = 'k'
    SM_LETTERSKIP   = 'l'
    MARK            = 'm'
    UNMARK          = 'M'
    PERM_FILTER     = 'p'
    SM_REGEX        = 'r'
    SMART_CASE      = 's'
    AS_YOU_TYPE     = 't'
    INVERT          = 'v'
    SW_ORDER        = 'w'

    OriginalSortSettings = {}

    def __init__(self, *args, **kws):
        Command.__init__(self, *args, **kws)
        self._regex = None
        self.flags, self.pattern = self.parse_flags()

    def execute(self):
        thisdir = self.fm.thisdir
        flags   = self.flags
        pattern = self.pattern
        regex   = self._build_regex()
        count   = self._count(move=True)

        self.fm.thistab.last_search = regex
        self.fm.set_search_method(order="search")

        if self.MARK in flags or self.UNMARK in flags:
            value = flags.find(self.MARK) > flags.find(self.UNMARK)
            if self.FILTER in flags:
                for f in thisdir.files:
                    thisdir.mark_item(f, value)
            else:
                for f in thisdir.files:
                    if regex.search(f.basename):
                        thisdir.mark_item(f, value)

        if self.PERM_FILTER in flags:
            thisdir.filter = regex if pattern else None

        # clean up:
        self.cancel()

        if self.OPEN_ON_ENTER in flags or \
                self.AUTO_OPEN in flags and count == 1:
            if os.path.exists(pattern):
                self.fm.cd(pattern)
            else:
                self.fm.move(right=1)

        if self.KEEP_OPEN in flags and thisdir != self.fm.thisdir:
            # reopen the console:
            if not pattern:
                self.fm.open_console(self.line)
            else:
                self.fm.open_console(self.line[0:-len(pattern)])

        if self.quickly_executed and thisdir != self.fm.thisdir and pattern != "..":
            self.fm.block_input(0.1)

    def cancel(self):
        if len(self.OriginalSortSettings) != 0:
            settings = self.fm.settings
            for name, value in self.OriginalSortSettings.iteritems():
                setattr(settings, name, value)
            self.OriginalSortSettings.clear()

        self.fm.thisdir.temporary_filter = None
        self.fm.thisdir.refilter()

    def quick(self):
        asyoutype = self.AS_YOU_TYPE in self.flags
        if self.FILTER in self.flags:
            self.fm.thisdir.temporary_filter = self._build_regex()
        if self.PERM_FILTER in self.flags and asyoutype:
            self.fm.thisdir.filter = self._build_regex()
        if self.FILTER in self.flags or self.PERM_FILTER in self.flags:
            self.fm.thisdir.refilter()
        if self.SW_ORDER in self.flags:
            ignoreCase = self.IGNORE_CASE in self.flags or (self.SMART_CASE in self.flags and self.pattern.islower())
            if ignoreCase:
                GlobalSmithWaterman.Pattern = self.pattern.lower()
                GlobalSmithWaterman.TransF = lambda item: item.basename_lower
            else:
                GlobalSmithWaterman.Pattern = self.pattern
                GlobalSmithWaterman.TransF = lambda item: item.basename

            settings = self.fm.settings
            tempSettings = {'sort': 'smith waterman', 'sort_reverse': True, 'sort_case_insensitive': ignoreCase, 'sort_directories_first': False}
            if settings.sort != tempSettings['sort']:
                self.OriginalSortSettings.update({name: getattr(settings, name) for name in tempSettings})
                for name, value in tempSettings.iteritems():
                    setattr(settings, name, value)

            thisdir = self.fm.thisdir
            thisdir.request_resort()
            thisdir.sort_if_outdated()
            thisdir.pointer = 0
            thisdir.pointed_obj = None if len(thisdir.files) == 0 else thisdir.files[0]
        if self._count(move=asyoutype) == 1 and self.AUTO_OPEN in self.flags:
            return True
        return False

    def tab(self):
        self.execute()
        #self._count(move=True, offset=1)

    def _build_regex(self):
        if self._regex is not None:
            return self._regex

        frmat   = "%s"
        flags   = self.flags
        pattern = self.pattern

        if pattern == ".":
            return re.compile("")

        # Handle carets at start and dollar signs at end separately
        if pattern.startswith('^'):
            pattern = pattern[1:]
            frmat = "^" + frmat
        if pattern.endswith('$'):
            pattern = pattern[:-1]
            frmat += "$"

        # Apply one of the search methods
        if self.SM_REGEX in flags:
            regex = pattern
        elif self.SM_GLOB in flags:
            regex = re.escape(pattern).replace("\\*", ".*").replace("\\?", ".")
        elif self.SM_LETTERSKIP in flags:
            regex = ".*".join(re.escape(c) for c in pattern)
        else:
            regex = re.escape(pattern)

        regex = frmat % regex

        # Invert regular expression if necessary
        if self.INVERT in flags:
            regex = "^(?:(?!%s).)*$" % regex

        # Compile Regular Expression
        options = re.LOCALE | re.UNICODE
        if self.IGNORE_CASE in flags or self.SMART_CASE in flags and \
                pattern.islower():
            options |= re.IGNORECASE
        try:
            self._regex = re.compile(regex, options)
        except:
            self._regex = re.compile("")
        return self._regex

    def _count(self, move=False, offset=0):
        count   = 0
        cwd     = self.fm.thisdir
        pattern = self.pattern

        if not pattern:
            return 0
        if pattern == '.':
            return 0
        if pattern == '..':
            return 1

        deq = deque(cwd.files)
        deq.rotate(-cwd.pointer - offset)
        i = offset
        regex = self._build_regex()
        for fsobj in deq:
            if regex.search(fsobj.basename):
                count += 1
                if move and count == 1:
                    cwd.move(to=(cwd.pointer + i) % len(cwd.files))
                    self.fm.thisfile = cwd.pointed_obj
            if count > 1:
                return count
            i += 1

        return count == 1

