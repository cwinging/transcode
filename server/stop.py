#!/usr/bin/python

import os
import sys
import signal
import time

dault_pidfile = '/home/swift/transcode/logs/transcode.pid'


def get_pid(pidfile):
    try:
        pf = file(pidfile, 'r')
        pid = int(pf.read().strip())
        pf.close()
    except IOError:
        pid = None
    except SystemExit:
        pid = None
    return pid

def stop(pidfile):
    """
    Stop the daemon
    """    
    print "Stopping..."

    # Get the pid from the pidfile
    pid = get_pid(pidfile)

    if not pid:
        message = "pidfile %s does not exist. Not running?\n"
        sys.stderr.write(message % pidfile)

        # Just to be sure. A ValueError might occur if the PID file is
        # empty but does actually exist
        if os.path.exists(pidfile):
            os.remove(pidfile)
        return  # Not an error in a restart

    # Try killing the daemon process
    try:
        i = 0
        while 1:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.1)
            i = i + 1
            if i % 10 == 0:
                os.kill(pid, signal.SIGHUP)
    except OSError, err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(pidfile):
                os.remove(pidfile)
        else:
            print str(err)
            sys.exit(1)

    print "Stopped"

if __name__ == '__main__':
    stop(dault_pidfile)