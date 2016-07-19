
if __name__ == '__main__':
    try:
        import os
        import sys

        args = sys.argv

        # find ['-p', '{path}']
        i = 1
        while True:
            try:
                i = args.index('-p', i)
            except ValueError:
                break

            i += 1
            if len(args) <= i:
                break
            path = args[i]

            # add path to sys.path
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            if path not in sys.path:
                sys.path.insert(0, path)

            i += 1


        # start client
        import external.rpcss as rpcss
        io = rpcss.EncryptedIO(sys.stdin, sys.stdout)

        null = open(os.devnull, 'w')
        sys.stdout = null
        sys.stderr = null

        client = rpcss.RpcClient(io)
        client.main()

    except Exception, e:
        import traceback
        with open('client.py.error', 'wb') as f:
            f.write(traceback.format_exc())

