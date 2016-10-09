
mkfifo jsonqueue.fifo
./piper.py jsonqueue.fifo | ./jsonqueue.py "$@" &
