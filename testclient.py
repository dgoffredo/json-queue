#!/usr/bin/env python

from __future__ import print_function

from socket import *
import json
import argparse
import code

def getOptions():
    parser = argparse.ArgumentParser(description='JSON queue test client')
    parser.add_argument('--host', default=gethostname(),
                        help='host to connect to (unless --socket specified)')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--port', type=int,
                       help='port to connect to')
    group.add_argument('--socket',
                       help='path to unix domain socket') 
    return parser.parse_args()

options = getOptions()

def sock():
    if options.socket is not None:
        s = socket(AF_UNIX, SOCK_STREAM)
        s.connect(options.socket)
    else:
        assert options.port is not None
        s = socket(AF_INET, SOCK_STREAM)
        s.connect((options.host, options.port))
    return s

s = sock()

def send_push(command, item):
    s.sendall('{} {}\n'.format(command, json.dumps(item).encode('utf-8')))

def push(item):
    send_push('push', item)
    return s.recv(4096)

def push_no_ack(item):
    send_push('push_no_ack', item)

def pop():
    s.sendall('pop\n')
    return s.recv(4096)

def count():
    s.sendall('count\n')
    return s.recv(4096)

def push_spam(howMany):
    for i in range(howMany):
        print(push(['spam', i]))

def push_no_ack_spam(howMany):
    for i in range(howMany):
        push_no_ack(['spam', i])

def pop_spam(howMany):
    for i in range(howMany):
        print(pop())

code.interact(banner='ctrl+d or quit() to quit.', local=locals())
