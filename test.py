import os
import subprocess

def is_mounted(server):
    output = subprocess.check_output(["mount"]).decode()
    return server in output


server = "sbc01/shares"
server_two = "sb06/shares"


for i in (server, server_two):
    print(is_mounted(i))