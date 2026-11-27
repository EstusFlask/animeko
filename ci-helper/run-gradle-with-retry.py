"""Retry Maven HTTP 429 failures with bounded backoff and preserve Gradle failures."""

import os
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
RATE_LIMIT = re.compile(r"Received status code 429\b|HTTP(?:/[\d.]+)?\s+429\b", re.IGNORECASE)


def run_once(command, cwd):
    rate_limited = False
    with subprocess.Popen(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    ) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            rate_limited = rate_limited or bool(RATE_LIMIT.search(line))
        status = process.wait()
    return status, rate_limited


def run_gradle(arguments, *, run=run_once, sleep=time.sleep):
    command = ([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "gradlew.bat"]
               if os.name == "nt" else ["./gradlew"]) + list(arguments)
    delays = (30, 60)
    for attempt in range(len(delays) + 1):
        status, rate_limited = run(command, ROOT)
        if status == 0 or not rate_limited or attempt == len(delays):
            return status
        delay = delays[attempt]
        print(f"::warning::Dependency repository returned HTTP 429; retrying in {delay} seconds", flush=True)
        sleep(delay)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(run_gradle(sys.argv[1:]))
