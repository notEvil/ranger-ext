# Smith-Waterman
## What is it ?

It's a modified version of ranger's builtin scout command. The new flag `w` enables a custom sorting method which uses the Smith-Waterman algorithm (slightly modified version of https://github.com/mengyao/Complete-Striped-Smith-Waterman-Library) to determine the degree of concordance between the file/directory names and the user input.

## Why ?

The Smith-Waterman algorithm is a great tool for fuzzy string matching. Typos or gaps are nuisances, not show stoppers. This extension is meant to be a navigation device, not a filter or selection tool.

## How to ?

- Run setup_ssw.sh

this should clone https://github.com/mengyao/Complete-Striped-Smith-Waterman-Library, apply a necessary patch and build the library.

- Include it in your commands.py somehow

see commands.py in the repository's root

- Create keymap in your rc.conf

I use `map i console scout -eksw`

- Add Complete-Striped-Smith-Waterman-Library/src to the environment variable LD_LIBRARY_PATH before starting ranger.

something like `LD_LIBRARY_PATH=/<path to>/Complete-Striped-Smith-Waterman-Library/src ranger`

## Details

- `<tab>` enters the directory/opens the file which is currently selected instead of moving the selection. This is my personal preference. If you have undeniable arguments I'm certainly open for change.
- I found no simple way to monkey patch the scout command to incorporate necessary adjustments. Therefore I will keep up with future changes to scout myself.

## Changes

- Previous versions used a slightly modified version of https://github.com/mbreese/swalign.
