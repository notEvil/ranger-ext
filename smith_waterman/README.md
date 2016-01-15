# Smith-Waterman
## What is it ?

It's a Command that matches user input against every file/directory name in the current directory.
Files/directories are then put in order of degree of concordance and the cursor is set to the first, best matching, file/directory.
Either an optimized version of the Smith-Waterman algorithm written in C is used (https://github.com/mengyao/Complete-Striped-Smith-Waterman-Library) or a pure python implementation (https://github.com/mbreese/swalign).

## Why ?

The Smith-Waterman algorithm is a great tool for fuzzy string matching.
Typos or gaps are nuisances, not show stoppers.
This extension is meant to be a navigation device, not a filter or selection tool.

## How to ?

- Run setup_ssw.sh (recommended) and/or setup_sw.sh

If these scripts fail at some point, do it manually.
(the patch is necessary, see for yourself ;)

- Add `smith_waterman.sw_nav` to your commands.py

See commands.py in the repository's root.

- Create keymap in your rc.conf

I use `map i console sw_nav -ekst%space`.

