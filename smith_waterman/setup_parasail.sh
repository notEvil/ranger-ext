#!/bin/bash -ev
git clone https://github.com/jeffdaily/parasail.git
mv parasail parasail-c
cd parasail-c
./configure
make -j $(nproc --all)
cd ..
git clone https://github.com/jeffdaily/parasail-python.git
ln -s parasail-python/parasail parasail
cd parasail-python/parasail
ln -s ../../parasail-c/.libs/libparasail.so.2.0.0 libparasail.so
cd ../..
