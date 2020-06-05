#!/usr/bin/env python3

from SchedulingService import server

if __name__ == '__main__':
    server.start()
    server.wait_for_termination()
