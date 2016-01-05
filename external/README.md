# External
## What is it ?

It's a collection of Commands and decorators based on the sub module rpcss.
At the moment there are:

- sudo
- copy/move
- delete
- make directory
- rename
- symbolic link
- hard link

rpcss (RPC secure stream) is a RPC-server-client implementation that uses encrypted binary IO streams for communication.
It facilitates the execution of (almost) arbitrary functions in a sub process.
A plain `RpcServer.call` will block until the result is available while `RpcServer.call_iter` (and `RpcServer.call_step`) takes a function returning an iterator/generator as argument and returns a generator of its own that yields the items that the client produces.
In the latter case the execution may be paused or stopped at any time.
Exceptions are transfered to the server and raised.

## Why ?

python does not support non-blocking file ops.
So ranger might stop reacting to user input if IO is slow.
The only solution is to delegate execution to some sub process.
The package multiprocessing offers a lot of functionality to achieve this, however in the context of a file manager one would often like to run things with elevated privileges.

## How to ?

- Include it in your commands.py somehow

see commands.py in the repository's root
- Create keymap in your rc.conf

I, for instance, use `map s<delete> console sudo delete` and `map spp sudo paste`.

## Details

- In general crucial low-level functions are replaced by decorated versions.
This way this extension does not depend on any implementation detail of ranger.
- But for one exception: `ranger.core.actions` from imports the `ranger.core.loader.CopyLoader` that is necessarily replaced.
- Every CopyLoader (on paste) starts a new sub process.
Inital cryptographic handshake may lead to a small delay.
- prints to stdout and stderr are completely dropped on client side.
Use `logging` for print debugging.

## Acknowledgments

- Oren Tirosh, monkey patch for pickle, http://code.activestate.com/recipes/572213-pickle-the-interactive-interpreter-state/

## News

Previous versions used a script called run_external.
Apart from security issues (unencrypted communication) there were some very unfortunate disadvantages.
First and foremost sub processes were spawned too often leading to bad performance especially on paste and delete.
And too much functionality of ranger had been duplicated.

