# Smith-Waterman
## What is it ?

It's a Command that matches user input against every file/directory name in the current directory.
Files/directories are then put in order of degree of concordance and the cursor is set to the first, best matching, file/directory.
The striped Smith-Waterman algorithm implemented in parasail (https://github.com/jeffdaily/parasail) and it's python binding parasail-python (https://github.com/jeffdaily/parasail-python) are used.
See references below.

## Why ?

The Smith-Waterman algorithm is a great tool for fuzzy string matching.
Typos or gaps are nuisances, not show stoppers.
This extension is meant to be a navigation device, not a filter or selection tool.

## How to ?

- Run setup_parasail.sh

If this script fails at some point, do it manually.

- Add `smith_waterman.sw_nav` to your commands.py

See commands.py in the repository root.

- Create keymap in your rc.conf

I use `map i console sw_nav -ekst%space`.

## References

Daily, Jeff. (2016). Parasail: SIMD C library for global, semi-global,
and local pairwise sequence alignments. *BMC Bioinformatics*, 17(1), 1-11.
doi:10.1186/s12859-016-0930-z

