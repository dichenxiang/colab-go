#!/usr/bin/env python3
"""
Kill zombie 'sshd: root' sessions on a Colab VM while keeping the sshd listener intact.
Colab only permits 1 concurrent SSH tunnel per runtime; run this via `colab exec -s <session> -f fix_remote_sshd.py`
whenever port forwarding gets stuck in 'reconnecting' or 'another connection active'.
"""
import subprocess

print("BEFORE:")
print(subprocess.getoutput("ps aux | grep sshd | grep -v grep"))
subprocess.getoutput("pkill -9 -f 'sshd: root'")
print("AFTER:")
print(subprocess.getoutput("ps aux | grep sshd | grep -v grep"))
