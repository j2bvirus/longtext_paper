"""Run a list of commands sequentially with a timestamped log (one queue per resource)."""
import datetime
import subprocess
import sys
import time

name, listfile = sys.argv[1], sys.argv[2]
log = open(f"runs/queue_{name}.log", "a", encoding="utf-8")


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


for line in open(listfile, encoding="utf-8"):
    cmd = line.strip()
    if not cmd or cmd.startswith("#"):
        continue
    log.write(f"{now()} START {cmd}\n")
    log.flush()
    t0 = time.time()
    p = subprocess.run(cmd, shell=True)
    log.write(f"{now()} END rc={p.returncode} {time.time() - t0:.0f}s {cmd}\n")
    log.flush()
log.write(f"{now()} QUEUE DONE\n")
