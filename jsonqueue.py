
from __future__ import print_function

import asyncore
import asynchat
import json
import socket
from collections import deque
import re
import sqlite3
import time
import sys

##################################
# SQL stuff for the queue server #
##################################

class SqlQueue(object):
    def __init__(self, fileName=':memory:', minCommitIntervalSeconds=10):
        self._lastCommitTime = 0 # Suitably past initial value.
        self._minCommitIntervalSeconds = minCommitIntervalSeconds

        self._db = sqlite3.connect(fileName)
        self._db.execute('create table if not exists Items('
                         'Id integer primary key, '
                         'Json text);')
        self._db_execute('vacuum;')
        self._commit()

        self._count = next(self._db.execute('select count(*) from Items;'))[0]

    def __len__(self):
        return self._count

    def push(self, jsonItem):
        self._db.execute('insert into Items(Json) values(?);', (jsonItem,))
        self._commit()
        self._count += 1

    def pop(self):
        if self._count == 0:
            raise Exception("Can't pop an item from an empty SqlQueue.")

        c = self._db.cursor()
       
        c.execute('select Id, Json from Items order by Id limit 1;')
        results = list(c)
        assert len(results) == 1
        rowId, jsonItem = results[0]
       
        c.execute('delete from Items where Id = ?;', (rowId,))
        self._commit()
        self._count -= 1

        return jsonItem.encode('utf-8')

    def _commit(self):
        # Since we assume that we have exclusive ownership of the database
        # file (we're the only connection), we don't need to suffer a file
        # system sync every time we want to commit. We can just *not* commit
        # most of the time, since uncommitted changes are always visible from
        # the connection that made them. Commit only if we haven't in a while.
        # This is to increase throughput.
        #
        now = time.time()
        if now - self._lastCommitTime >= self._minCommitIntervalSeconds:
            self._db.commit()
            self._lastCommitTime = now

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._db.commit()
        self._db.close()

#####################################
# Server stuff for the queue server #
#####################################

MESSAGE_TERMINATOR = '\n'

def nonifyAll(value, q):
    for i, item in enumerate(q):
        if item == value:
            q[i] = None

def compactJson(obj):
    return json.dumps(obj, separators=(',',':')).encode('utf-8')

# Returns a compact version of 'string'.
# Throws if 'string' is not valid json.
def formatJson(string):
    return compactJson(json.loads(string))

lexerPattern = r'^\s*(?P<command>\w+)(\s+(?P<payload>\S.*))?\s*$'
messageLexer = re.compile(lexerPattern)

# str -> (str, json-str) or raise Exception.
def parseMessage(message):
    match = messageLexer.match(message)
    if not match:
        raise Exception('Message does not match the'
                        ' regular expression: {}'.format(lexerPattern))

    groups = match.groupdict()
    command, payload = groups['command'].lower(), groups['payload']
    if payload is not None:
        payload = formatJson(payload)

    debug(command, payload)
    return command, payload

# Return the first non-None value popped from 'q',
# or None if there is no such element.
def popSkipNones(q):
    item = None
    while len(q) != 0 and item is None:
        item = q.pop()

    return item

# One conversation with a client.
#
class Channel(asynchat.async_chat):
    def __init__(self, sock, popWaitQueue, jsonQueue):
        asynchat.async_chat.__init__(self, sock=sock)
        self.set_terminator(MESSAGE_TERMINATOR)
        self._buffer = []
        self._popWaitQueue = popWaitQueue
        self._jsonQueue = jsonQueue
        self._waitingCount = 0 # How many times 'self' appears in popWaitQueue.

    def collect_incoming_data(self, data):
        debug(self, 'has data', data)
        self._buffer.append(data)

    def found_terminator(self):
        message = ''.join(self._buffer)
        debug(self, 'encountered a statement:', message)
        del self._buffer[:]

        try:
            self.handleCommand(*parseMessage(message))
        except Exception as e:
            self.reportError(e.message)            
            raise

    # 'jsonItem' might be None, if this is a "pop."
    def handleCommand(self, command, jsonItem):
        if command in ('push', 'push_no_ack'):
            # If there's someone waiting to pop an item, give it to them.
            popper = popSkipNones(self._popWaitQueue)
            if popper is None:                 # Nobody waiting
                self._jsonQueue.push(jsonItem)
            else:                              # Give it to the guy waiting
                popper.popReady(jsonItem)
            if command != 'push_no_ack':
                self.push('ok\n')
        elif command == 'pop':
            if len(self._jsonQueue) == 0:
                debug('Putting', self, 'on the wait queue.')
                self._popWaitQueue.appendleft(self)
                self._waitingCount += 1
            else:
                self.push(self._jsonQueue.pop() + '\n')
        elif command == 'count':
            self.push('{}\n'.format(len(self._jsonQueue)))
        else:
            self.reportError('Unknown command "{}"'.format(command))

    def handle_close(self):
        debug(self, 'going away.')
        nonifyAll(self, self._popWaitQueue)
        self.close() # Do this to prevent infinite loop.

    def popReady(self, jsonItem):
        debug(self, 'got something after waiting:', jsonItem)
        assert self._waitingCount > 0
        self._waitingCount -= 1
        self.push(jsonItem + '\n')

    def reportError(self, message):
        self.push('error {}\n'.format(json.dumps(message)))

def connectionBacklogSize():      
    # There is some discussion online about the correct 'backlog'
    # value for listen(). The value below was added to python 3.x
    # at some point, so I use it here. The idea is that 5 is a
    # a typical number, but ideally you'd like to support more
    # backlog so that incoming connections are not dropped.
    # socket.SOMAXCONN seems like a reasonable value, but on some
    # platforms it's something like 2**16, which could use way too
    # much memory in the kernel. The compromise is to use
    # socket.SOMAXCONN, but to limit the value to at most 128.
    #
    return min(128, socket.SOMAXCONN)

# The connection handler for the socket on which this script is listening. 
#
class Server(asyncore.dispatcher):
    def __init__(self, localAddress, popWaitQueue, jsonQueue):
        self._popWaitQueue = popWaitQueue
        self._jsonQueue = jsonQueue

        # 'localAddress' is either a string filename of a unix domain socket,
        # or otherwise a local integer port for TCP.
        #
        if isinstance(localAddress, basestring):
            address, domain = localAddress, socket.AF_UNIX
        else:
            port = localAddress
            address, domain = (socket.gethostname(), port), socket.AF_INET

        asyncore.dispatcher.__init__(self)
        self.create_socket(domain, socket.SOCK_STREAM)
        self.bind(address)
        self.listen(connectionBacklogSize())
     
    def handle_accept(self):
        peer = self.accept()
        if peer is None:
            return # Connection didn't take place: ignore event.
        
        # If we're listening on an AF_INET socket, then address with be the
        # ip of the peer. If we're listening on an AF_UNIX socket, then it
        # will be None.
        sock, address = peer
        debug('Incoming connection from', address)
        Channel(sock, self._popWaitQueue, self._jsonQueue)

############################################################
# Main server logic (command line parsing, open port, etc. #
############################################################

# debug = print # for debugging

def debug(*args, **kwargs):
    pass # for production

Queue = SqlQueue

popWaitQueue = deque()
with Queue(sys.argv[1]) as jsonQueue:
    Server(1337, popWaitQueue, jsonQueue)
    asyncore.loop(use_poll=True)
