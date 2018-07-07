#!/bin/bash -ev
self=$(dirname "$(realpath "$0")")

cp -t "$HOME/.config/ranger" "$self/smith_waterman.py"

pip3 install --user wheel
sudo apt install -y automake libtool-bin # parasail uses a version which doesn't compile
pip3 install --user parasail

# add
#
# import smith_waterman
# sw_nav = smith_waterman.sw_nav
# 
# to $HOME/.config/ranger/commands.py and
# 
# map {key} console sw_nav {flags}%space
# 
# with {key} and flags replaced to $HOME/.config/ranger/rc.conf

read -p "Press ENTER to continue"
