
>/dev/null 2>&1 mkfifo jsonqueue.fifo
./piper.py jsonqueue.fifo | ./jsonqueue.py "$@" &
