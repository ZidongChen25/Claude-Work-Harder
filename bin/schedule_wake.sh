#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="$ROOT/config.yaml"
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found" >&2; exit 1
fi
if ! command -v pmset >/dev/null 2>&1; then
  echo "pmset not found" >&2; exit 1
fi

read_cfg() {
  python3 - "$CFG" <<'PY'
import sys, re
from pathlib import Path
p = Path(sys.argv[1])
s = p.read_text()
start = re.search(r"start_time:\s*\"?(\d{2}:\d{2})\"?", s)
weekdays = re.search(r"weekdays:\s*([A-Za-z]+)", s)
print((start.group(1) if start else "06:00"), (weekdays.group(1) if weekdays else "MTWRFSU"))
PY
}

START_TIME=$(read_cfg | awk '{print $1}')
DAYS=$(read_cfg | awk '{print $2}')
# Wake 2 minutes earlier
H=${START_TIME%:*}
M=${START_TIME#*:}
MM=$((10#$M))
HH=$((10#$H))
if [ $MM -ge 2 ]; then WM=$((MM-2)); WH=$HH; else WM=$((MM+58)); WH=$(( (HH+23)%24 )); fi
WAKE=$(printf "%02d:%02d:00" "$WH" "$WM")

echo "Scheduling pmset repeat wakeorpoweron $DAYS $WAKE"
if [ "$EUID" -ne 0 ]; then
  echo "This command needs sudo: sudo pmset repeat wakeorpoweron $DAYS $WAKE" >&2
  exit 1
fi
pmset repeat wakeorpoweron "$DAYS" "$WAKE"
pmset -g sched 