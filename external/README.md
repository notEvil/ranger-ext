# External
## What is it ?

It's a collection of Commands which are based on the sub module run_external. At the moment there are:

- sudo
- paste
- delete
- rename
- mkdir

run_external facilitates the execution of (almost) arbitrary functions in a sub process. Results as well as stdout/stderr prints and exceptions are transfered to the calling process using flavoured stdout/stderr. If the function returns a generator then the sub process continues generating and transfering items to the calling process. In this case execution may also be paused or terminated. For instance, the process spawned by paste reports the progress every now and then, and pasting may be paused at any moment.

## Why ?

python does not support non-blocking file ops. So ranger might stop reacting to user input if IO is slow. The only solution is to delegate execution to some sub process. The package multiprocessing offers a lot of functionality to achieve this, however in the context of a file manager one would often like to run things with elevated privileges.

## How to ?

- Include it in your commands.py somehow

see commands.py in the repository's root
- Create keymap in your rc.conf

I for instance use `map s<delete> console sudo delete` and `map sp sudo paste`.

## Details

- paste is based on ranger's CopyLoader and replicates its functionality. I couldn't find a nice way to prevent this.
- delete masks os.remove and shutil.rmtree such that they are executed in a sub process whenever they are called. Then ranger's delete function gets executed and finally os.remove and shutil.rmtree are unmasked again.

## Acknowledgments

- Oren Tirosh, monkey patch for pickle, http://code.activestate.com/recipes/572213-pickle-the-interactive-interpreter-state/
