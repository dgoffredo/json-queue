# json-queue
A dead simple queue server for JSON data

## example

    $ mkfifo admin-pipe

    $ ./piper.py admin-pipe | ./jsonqueue.py --port 1337 &
    Building database...
    Ready.

    $ >admin-pipe echo "echo jsonqueue responding to an admin command"
    jsonqueue responding to an admin command

    $ ./testclient.py --port 1337
    ctrl+d or quit() to quit.
    >>> count()
    '0\n'
    >>> push({"some": "data", "and": [2, "stuffs"]})
    'ok\n'
    >>> pop()
    '{"and":[2,"stuffs"],"some":"data"}\n'
    >>> quit()

    $ >admin-pipe echo exit 
    Exiting.

    $

## --help

    $ python jsonqueue.py --help
    usage: jsonqueue.py [-h] (--port PORT | --socket SOCKET) [database]

    JSON queue server

    positional arguments:
      database         path to database file

    optional arguments:
      -h, --help       show this help message and exit
      --port PORT      port to listen on
      --socket SOCKET  path to unix domain socket
