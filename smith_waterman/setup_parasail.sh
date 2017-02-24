#!/bin/bash -ev
if [ -d "./parasail-c" ]; then
    git -C "./parasail-c" pull
else
    git clone https://github.com/jeffdaily/parasail.git
    mv parasail parasail-c
fi
pushd parasail-c
./configure
make -j $(nproc --all)
popd
if [ -d "./parasail-python" ]; then
    git -C "./parasail-python" pull
else
    git clone https://github.com/jeffdaily/parasail-python.git
fi
mv -b parasail parasail.bak || true
ln -s parasail-python/parasail parasail
pushd parasail-python/parasail
mv -b libparasail.so libparasail.so.bak || true
ln -s ../../parasail-c/.libs/libparasail.so.2.0.0 libparasail.so
popd
