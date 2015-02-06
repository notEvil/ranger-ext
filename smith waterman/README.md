# What is it ?

It's a special kind of the scout command. The user input is matched against every file/directory name, using a slightly modified version of @mbreese's swalign (https://github.com/mbreese/swalign). The files/directories are then sorted by the Smith-Waterman score such that the best matches are on top.

# Why ?

The Smith-Waterman algorithm is a great tool which allows fuzzy matching such that typos don't kill your search. It is meant to be a navigation device, not a filter or selection tool.

# How to ?

- Include it in your commands.py somehow

see commands.py in the repository's root
- Create keymap in your rc.conf

I use `map i console scout -eksw`

# Details

- Sorting is accomplished by a directory sort method which is enabled/disabled when necessary
- I found no simple way to monkey patch the scout command to incorporate necessary adjustments. Therefore I will keep up with future changes to scout myself.
