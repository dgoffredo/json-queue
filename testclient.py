
from socket import *
import json

def sock():
    s = socket(AF_INET, SOCK_STREAM)
    s.connect((gethostname(), 1337))
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
