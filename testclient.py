
from socket import *
import json
import argparse

def getOptions():
    parser = argparse.ArgumentParser(description='JSON queue server')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--port', type=int,
                       help='port to listen on')
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
        s.connect((gethostname(), options.port))
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

def pop_spam(howMany):
    for i in range(howMany):
        print(pop())
