# Smith-Waterman
## What is it ?

It's a Command that matches user input against every file/directory name in the current directory.
Files/directories are then put in order of degree of concordance and the cursor is set to the first, best matching, file/directory.
It uses the striped Smith-Waterman algorithm implemented in parasail (https://github.com/jeffdaily/parasail) and made available by parasail-python (https://github.com/jeffdaily/parasail-python).
See references below.

## Why ?

The Smith-Waterman algorithm is a great tool for fuzzy string matching.
Typos or gaps are nuisances, not show stoppers.
This extension is meant to be a navigation device, not a filter or selection tool.

## How to ?

- Run install.sh and follow the instructions.

It currently tries to install automake and libtool-bin because `pip3 install --user parasail` fails due to the version of automake that parasail tries to temporarily set up.

It assumes python 3 and installs python packages with `--user`.

I use `map i console sw_nav -ekst%space` as key map in rc.conf.

## References

Daily, Jeff. (2016). Parasail: SIMD C library for global, semi-global,
and local pairwise sequence alignments. *BMC Bioinformatics*, 17(1), 1-11.
doi:10.1186/s12859-016-0930-z
