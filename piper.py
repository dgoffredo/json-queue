#!/usr/bin/env python

# The idea behind this script is that you want to forward lines from a pipe
# without also forwarding EOF whenever a writer closes the write end of the
# pipe. This script acts as a middle man, absorbing "hangup" events from the
# pipe and forwarding only data to stdout.
#
# This script will terminate when its stdout emits an error or hangs up,
# i.e. whenever the downstream process goes away or closes my stdout.

from __future__ import print_function

import sys
import argparse
import select
import fcntl
import os
from multiprocessing import Process

def getOptions():
    parser = argparse.ArgumentParser(description='Monitor fifo for lines')
    parser.add_argument('pipePath', help='path to fifo pipe')
    return parser.parse_args()

options = getOptions()

def setNonblocking(f):
    flag = fcntl.fcntl(f, fcntl.F_GETFL)
    fcntl.fcntl(f, fcntl.F_SETFL, flag | os.O_NONBLOCK)

setNonblocking(sys.stdout)

def openNonblocking(filePath):
    f = open(filePath)
    setNonblocking(f)
    return f

# Spawn a subprocess to open the pipe for writing. This is just so we can open
# the same pipe for reading, without being blocked on open(). Then we join()
# with the subprocess and continue.
#
process = Process(target=lambda: open(options.pipePath, 'w').close())
process.start()

inPipe = openNonblocking(options.pipePath)

# I will also separately open the same pipe for writing. I don't plan to be
# doing any writing, but this is necessary to prevent the system from spamming
# me with POLLHUP (hang up) events when a writer closes the pipe. Having the
# file open for writing like this ensures that as long as I'm around, the pipe
# has at least one writer and so POLLHUP won't happen.
# Opening 'inPipe' as 'rw' is not enough, for some reason. I need the separate
# file handle.
#
inPipeWrite = open(options.pipePath, 'w')

process.join()

pollster = select.poll()

suffixes = ['IN', 'PRI', 'OUT', 'ERR', 'HUP', 'NVAL']
class Events:
    pass
for suffix in suffixes:
    setattr(Events, suffix, getattr(select, 'POLL' + suffix))

pollster.register(inPipe)

stdoutMask = Events.NVAL
pollster.register(sys.stdout, stdoutMask)

files = { f.fileno(): f for f in (inPipe, sys.stdout) }

buffer = []

while True:
    for fd, eventId in pollster.poll():
        f = files[fd]
 
        # print('file {} got event {}'.format(f, eventId), file=sys.stderr)

        if f == inPipe:
            if eventId & Events.IN:
                buffer += f.read(select.PIPE_BUF)
                stdoutMask |= Events.OUT
                pollster.modify(sys.stdout, stdoutMask)
                # print('buffer:', buffer, file=sys.stderr)
        elif f == sys.stdout:
            if eventId & Events.HUP:
                # print('Downstream hung up. Exiting', file=sys.stderr)
                sys.exit()
            if eventId & Events.ERR:
                # print('Downstream error. Exiting', file=sys.stderr)
                sys.exit()
            if eventId & Events.OUT and buffer:
                # print('*** Time to write my buffer.', file=sys.stderr)
                f.write(''.join(buffer[:select.PIPE_BUF]))
                f.flush()
                del buffer[:select.PIPE_BUF]
                if len(buffer) == 0:
                    stdoutMask &= ~Events.OUT
                    pollster.modify(sys.stdout, stdoutMask)
                # print('Remaining buffer:', buffer, file=sys.stderr)
