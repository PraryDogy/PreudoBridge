# watchdog.py
import os, signal, time, sys

pid = int(sys.argv[1])
time.sleep(3)
os.kill(pid, signal.SIGKILL)
