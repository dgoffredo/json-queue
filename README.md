# json-queue
A dead simple message queue server for JSON data

![a Jason queue](banner.jpg)

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

## client protocol

It's a line based protocol. The table below is from a client's point of view.
Any whitespace immediately preceeding the newline character may be omitted.

| Operation       | Direction | Format                  |
| ---------       | --------- | ------                  |
| push            | write     | `push <JSON> \n`        |
|                 | read      | `ok \n`                 |
| push_no_ack     | write     | `push_no_ack <JSON> \n` |
| pop             | write     | `pop \n`                |
|                 | read      | `<JSON text> \n`        |
| count           | write     | `count \n`              |
|                 | read      | `<integer> \n`          |


## admin commands

Administrative commands are issued to the JSON queue server by writing lines
to its stdin. It's a line based protocol. Output diagnostics are printed to
the server's stderr.

| Command                              | Effect
| -------                              | ------
| `echo <text> \n`            | Print the specified text to stderr.
| `purge <integer> \n` | Pop up to the specified number of items from the queue and discard them. Print to stderr the number discarded. |
| `purge \n`                              | Pop all of the queue's items and discard them. Print to stderr the number discarded. |
| `count \n` | Print to stderr the number of items currently in the queue. |
| `debug <setting> \n` | Enable/disable debugging trace. The setting may be one of `on`, `yes`, or `enable` to enable; or, one of `off`, `no`, or `disable` to disable. |
| `exit \n`                               | Shut down the server and exit the process. |

