#!/usr/bin/env python3
import subprocess
import time
import datetime as dt
import os
import sys
import json
import signal
import re
import platform
from pathlib import Path
from zoneinfo import ZoneInfo

try:
	import yaml  # PyYAML
except Exception as e:
	print("PyYAML not installed. Please add 'PyYAML' to requirements and install.", file=sys.stderr)
	yaml = None

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# Platform-specific paths
if IS_WINDOWS:
	APP_ROOT = Path(__file__).parent.resolve()
	CONFIG_PATH = APP_ROOT / "config.yaml"
	LOG_PATH = Path.home() / "AppData/Local/claude-scheduler.log"
else:
	# Avoid hardcoded user-specific paths. Allow override via environment
	# variable CLAUDE_SCHEDULER_ROOT, otherwise use the script directory.
	APP_ROOT = Path(os.environ.get("CLAUDE_SCHEDULER_ROOT", Path(__file__).parent)).resolve()
	CONFIG_PATH = APP_ROOT / "config.yaml"
	LOG_PATH = Path.home() / "Library/Logs/claude-scheduler.log"

DEFAULT_CONFIG = {
	"timezone": "Europe/London",
	"start_time": "06:00",
	"sleep_time": "23:00",
	"weekdays": "MTWRFSU",
	"kickoff_prompt": "ping",
	"use_caffeinate": True,
	"force_sleep_at_quiet_hours": False,
	"pre_caffeinate_minutes": 2,
}

WEEKDAY_MAP = {
	"M": 0,  # Monday
	"T": 1,
	"W": 2,
	"R": 3,  # Thursday
	"F": 4,
	"S": 5,  # Saturday
	"U": 6,  # Sunday
}


def log(message: str, data: dict | None = None) -> None:
	LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
	ts = dt.datetime.now().isoformat(timespec="seconds")
	line = {"ts": ts, "msg": message}
	if data is not None:
		line.update(data)
	with LOG_PATH.open("a") as f:
		f.write(json.dumps(line, ensure_ascii=False) + "\n")


def load_config() -> dict:
	cfg = DEFAULT_CONFIG.copy()
	try:
		if CONFIG_PATH.exists():
			with CONFIG_PATH.open("r") as f:
				file_cfg = yaml.safe_load(f) if yaml else {}
				if isinstance(file_cfg, dict):
					cfg.update(file_cfg)
	except Exception as e:
		log("config_load_error", {"error": str(e)})
	return cfg


def parse_hhmm(s: str) -> tuple[int, int]:
	parts = s.strip().split(":")
	return int(parts[0]), int(parts[1])


def in_active_day(cfg: dict, now_local: dt.datetime) -> bool:
	wd = now_local.weekday()
	wdset = set()
	w = cfg.get("weekdays", "MTWRFSU").upper()
	if w == "WEEKDAYS":
		wdset = {0,1,2,3,4}
	else:
		for ch in w:
			if ch in WEEKDAY_MAP:
				wdset.add(WEEKDAY_MAP[ch])
	return wd in wdset


def run_cmd(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
	try:
		# On Windows, try multiple encodings to handle different command outputs
		if IS_WINDOWS:
			# Try common Windows encodings: cp936 (Chinese), gbk, utf-8
			encodings_to_try = ['cp936', 'gbk', 'utf-8', 'latin1']
			
			for encoding in encodings_to_try:
				try:
					res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding=encoding, errors='replace')
					# If we get here without exception, the encoding worked
					return res.returncode, res.stdout, res.stderr
				except (UnicodeDecodeError, LookupError):
					continue
			
			# If all encodings fail, fall back to bytes and decode with replacement
			res = subprocess.run(cmd, capture_output=True, timeout=timeout)
			stdout = res.stdout.decode('utf-8', errors='replace') if res.stdout else ''
			stderr = res.stderr.decode('utf-8', errors='replace') if res.stderr else ''
			return res.returncode, stdout, stderr
		else:
			res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
			return res.returncode, res.stdout, res.stderr
	except Exception as e:
		return 1, "", str(e)


def send_claude(prompt: str, model: str | None, timeout: int = 60) -> bool:
	# On Windows, use full path to ensure claude is found in scheduled task environment
	if IS_WINDOWS:
		claude_path = os.path.expanduser(r"~\AppData\Roaming\npm\claude.cmd")
		if not os.path.exists(claude_path):
			claude_path = "claude"  # Fall back to PATH if full path doesn't exist
	else:
		claude_path = "claude"
	
	cmd = [claude_path, "-p", prompt, "--output-format", "json"]
	# If model is provided and not "default", pass it through; else rely on CLI default
	if model and model.strip().lower() != "default":
		cmd += ["--model", model]
	rc, out, err = run_cmd(cmd, timeout=timeout)
	log("send_claude", {"rc": rc, "stdout": out[-3000:], "stderr": err[-1000:], "cmd": " ".join(cmd)})
	return rc == 0

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

def strip_ansi(text: str) -> str:
	return ANSI_RE.sub("", text or "")

RESET_PATTERNS = [
	re.compile(r"Limit\s+resets\s+at\s*[:\-]?\s*(\d{1,2}:\d{2})\s*(a\.m\.|p\.m\.|AM|PM)", re.I),
	re.compile(r"Limit\s+resets\s+at\s*[:\-]?\s*(\d{2}):(\d{2})", re.I),
	re.compile(r"Time\s*to\s*Reset\s*[:\-]?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?", re.I),
	re.compile(r"Time\s*to\s*Reset\s*[:\-]?\s*(\d+)\s*h\s*(\d+)?\s*m", re.I),
]


def parse_reset(stdout: str, tz: ZoneInfo) -> dt.datetime | None:
	out = strip_ansi(stdout)
	now = dt.datetime.now(tz)
	m = RESET_PATTERNS[0].search(out)
	if m:
		tstr = m.group(1); ap = m.group(2)
		ap_fixed = ap.replace("a.m.", "AM").replace("p.m.", "PM").upper()
		when = dt.datetime.strptime(f"{tstr} {ap_fixed}", "%I:%M %p").time()
		target = now.replace(hour=when.hour, minute=when.minute, second=0, microsecond=0)
		if target <= now: target += dt.timedelta(days=1)
		return target
	m = RESET_PATTERNS[1].search(out)
	if m:
		hh = int(m.group(1)); mm = int(m.group(2))
		target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
		if target <= now: target += dt.timedelta(days=1)
		return target
	m = RESET_PATTERNS[2].search(out)
	if m:
		h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
		return now + dt.timedelta(hours=h, minutes=mi, seconds=s)
	m = RESET_PATTERNS[3].search(out)
	if m:
		h, mi = int(m.group(1)), int(m.group(2) or 0)
		return now + dt.timedelta(hours=h, minutes=mi)
	return None


def get_next_reset(tz: ZoneInfo, backoff_start: float = 2.0, backoff_max: float = 60.0) -> dt.datetime:
	"""Runs claude-monitor and parses the next reset. Falls back to now+5h."""
	sleep_s = backoff_start
	while True:
		# Platform-specific command execution
		if IS_WINDOWS:
			# Try multiple possible locations for claude-monitor on Windows
			claude_monitor_paths = [
				os.path.expanduser(r"~\miniconda3\Scripts\claude-monitor.exe"),
				os.path.expanduser(r"~\.local\bin\claude-monitor.exe"),
				"claude-monitor"  # Fall back to PATH
			]
			
			rc, out, err = None, "", ""
			for monitor_path in claude_monitor_paths:
				try:
					if monitor_path != "claude-monitor" and not os.path.exists(monitor_path):
						continue
					rc, out, err = run_cmd([monitor_path, "--clear"], timeout=20)
					break
				except Exception as e:
					continue
			
			if rc is None:  # All paths failed
				rc, out, err = run_cmd(["claude-monitor", "--clear"], timeout=20)
		else:
			# macOS/Linux implementation
			rc, out, err = run_cmd(["bash","-lc","claude-monitor --clear"], timeout=20)
		
		combined = out or err
		parsed = parse_reset(combined, tz)
		log("monitor_parse", {"rc": rc, "parsed": parsed.isoformat() if parsed else None, "snippet": strip_ansi(combined)[-1200:]})
		if parsed:
			return parsed
		# Backoff and retry a few times, then fallback
		if sleep_s > backoff_max:
			return dt.datetime.now(tz) + dt.timedelta(hours=5)
		time.sleep(sleep_s)
		sleep_s *= 1.7


def ensure_caffeinate(enabled: bool) -> subprocess.Popen | None:
	if not enabled:
		return None
	
	if IS_WINDOWS:
		return ensure_caffeinate_windows(enabled)
	else:
		# macOS implementation
		try:
			proc = subprocess.Popen(["caffeinate","-dimsu"])  # stop explicitly at quiet hours
			log("caffeinate_started", {"pid": proc.pid})
			return proc
		except Exception as e:
			log("caffeinate_error", {"error": str(e)})
			return None

def ensure_caffeinate_windows(enabled: bool) -> subprocess.Popen | None:
	if not enabled:
		return None
	# Windows: Use powercfg to prevent system sleep
	try:
		# Create a power request to prevent system idle sleep
		subprocess.run(["powercfg", "/requestsoverride", "PROCESS", "python.exe", "SYSTEM"], check=True)
		log("windows_caffeinate_started", {"method": "powercfg_requestsoverride"})
		return None  # Windows doesn't return a process like macOS
	except Exception as e:
		log("windows_caffeinate_error", {"error": str(e)})
		return None


def stop_caffeinate(proc: subprocess.Popen | None) -> None:
	if IS_WINDOWS:
		stop_caffeinate_windows()
		return
	
	if not proc:
		return
	try:
		if proc.poll() is None:
			proc.terminate()
			try:
				proc.wait(timeout=3)
			except Exception:
				proc.kill()
		log("caffeinate_stopped", {"pid": getattr(proc, "pid", None)})
	except Exception as e:
		log("caffeinate_stop_error", {"error": str(e)})

def stop_caffeinate_windows() -> None:
	try:
		# Remove the power request override
		subprocess.run(["powercfg", "/requestsoverride", "PROCESS", "python.exe"], check=True)
		log("windows_caffeinate_stopped", {"method": "powercfg_requestsoverride_removed"})
	except Exception as e:
		log("windows_caffeinate_stop_error", {"error": str(e)})


def maybe_force_sleep(enabled: bool) -> None:
	if not enabled:
		return
	
	if IS_WINDOWS:
		maybe_force_sleep_windows(enabled)
	else:
		# macOS implementation
		try:
			rc, out, err = run_cmd(["sudo","pmset","sleepnow"], timeout=5)
			log("pmset_sleepnow", {"rc": rc, "stdout": out, "stderr": err})
		except Exception as e:
			log("pmset_sleep_error", {"error": str(e)})

def maybe_force_sleep_windows(enabled: bool) -> None:
	if not enabled:
		return
	try:
		# Use Windows shutdown command to hibernate (closest to macOS sleep)
		rc, out, err = run_cmd(["shutdown", "/h"], timeout=5)
		log("windows_hibernate", {"rc": rc, "stdout": out, "stderr": err})
	except Exception as e:
		log("windows_sleep_error", {"error": str(e)})


def validate_pmset(expected_time: str) -> None:
	if IS_WINDOWS:
		validate_windows_schedule(expected_time)
	else:
		# macOS implementation
		rc, out, err = run_cmd(["pmset","-g","sched"], timeout=5)
		ok = expected_time in (out or "")
		log("pmset_sched", {"rc": rc, "ok": ok, "snippet": (out or err)[-1200:]})

def validate_windows_schedule(expected_time: str) -> None:
	try:
		# Check Windows Task Scheduler for our wake task
		rc, out, err = run_cmd(["schtasks", "/query", "/tn", "ClaudeSchedulerWake", "/fo", "LIST"], timeout=5)
		ok = expected_time in (out or "")
		log("windows_sched", {"rc": rc, "ok": ok, "snippet": (out or err)[-1200:]})
	except Exception as e:
		log("windows_sched_error", {"error": str(e)})


def wait_until(target: dt.datetime) -> None:
	while True:
		now = dt.datetime.now(target.tzinfo)
		d = (target - now).total_seconds()
		if d <= 0:
			return
		time.sleep(min(60, max(1, d)))


def next_daily_in_window(now: dt.datetime, start_hm: tuple[int,int], tz: ZoneInfo) -> dt.datetime:
	h, m = start_hm
	t = now.replace(hour=h, minute=m, second=0, microsecond=0)
	if t <= now:
		t += dt.timedelta(days=1)
	return t


def daemon_loop():
	cfg = load_config()
	tz = ZoneInfo(cfg.get("timezone", DEFAULT_CONFIG["timezone"]))
	start_hm = parse_hhmm(cfg.get("start_time", DEFAULT_CONFIG["start_time"]))
	sleep_hm = parse_hhmm(cfg.get("sleep_time", DEFAULT_CONFIG["sleep_time"]))
	pre_min = int(cfg.get("pre_caffeinate_minutes", DEFAULT_CONFIG["pre_caffeinate_minutes"]))
	caffeinate_proc: subprocess.Popen | None = None
	validate_pmset(cfg.get("start_time", DEFAULT_CONFIG["start_time"]))

	log("daemon_started", {"cfg": cfg})
	model = cfg.get("model")  # Optional: if None or "default", use CLI default
	prompt = cfg.get("kickoff_prompt", DEFAULT_CONFIG["kickoff_prompt"]) or "ping"

	while True:
		now = dt.datetime.now(tz)
		if not in_active_day(cfg, now):
			# Ensure caffeinate is not running outside active days
			stop_caffeinate(caffeinate_proc)
			caffeinate_proc = None
			# Sleep until next day start
			next_start = next_daily_in_window(now, start_hm, tz)
			log("inactive_day_wait", {"until": next_start.isoformat()})
			wait_until(next_start)
			continue

		# Compute today's times
		today_start = now.replace(hour=start_hm[0], minute=start_hm[1], second=0, microsecond=0)
		pre_start = today_start - dt.timedelta(minutes=max(0, pre_min))

		# If before start_time, pre-start caffeinate N minutes earlier
		if now < today_start:
			if cfg.get("use_caffeinate", True):
				if now < pre_start:
					log("waiting_for_pre_start", {"until": pre_start.isoformat()})
					wait_until(pre_start)
					now = dt.datetime.now(tz)
				# Start caffeinate if not already
				if caffeinate_proc is None or caffeinate_proc.poll() is not None:
					caffeinate_proc = ensure_caffeinate(True)
			log("waiting_for_start", {"until": today_start.isoformat()})
			wait_until(today_start)
			now = dt.datetime.now(tz)

		# Start caffeinate for active window if enabled (in case not started earlier)
		if cfg.get("use_caffeinate", True) and (caffeinate_proc is None or caffeinate_proc.poll() is not None):
			caffeinate_proc = ensure_caffeinate(True)

		# Kickoff
		log("kickoff", {"at": now.isoformat()})
		send_claude(prompt, model, timeout=60)

		# Work until sleep_time
		while True:
			now = dt.datetime.now(tz)
			today_sleep = now.replace(hour=sleep_hm[0], minute=sleep_hm[1], second=0, microsecond=0)
			if now >= today_sleep:
				log("entering_quiet_hours", {"at": now.isoformat()})
				# Stop caffeinate at quiet hours
				stop_caffeinate(caffeinate_proc)
				caffeinate_proc = None
				maybe_force_sleep(bool(cfg.get("force_sleep_at_quiet_hours", False)))
				break

			# Find next reset and re-prime
			next_reset = get_next_reset(tz)
			buffered = next_reset + dt.timedelta(seconds=3)
			log("sleep_until_reset", {"reset": next_reset.isoformat(), "buffered": buffered.isoformat()})
			wait_until(buffered)
			send_claude(prompt, model, timeout=60)

		# After quiet hours, ensure caffeinate remains stopped and wait until next day's start
		stop_caffeinate(caffeinate_proc)
		caffeinate_proc = None
		next_start = next_daily_in_window(dt.datetime.now(tz), start_hm, tz)
		log("waiting_next_day", {"until": next_start.isoformat()})
		wait_until(next_start)

	# Not reachable


if __name__ == "__main__":
	try:
		daemon_loop()
	except KeyboardInterrupt:
		log("shutdown", {"signal": "KeyboardInterrupt"})
		sys.exit(0)
	except Exception as e:
		log("fatal_error", {"error": str(e)})
		raise 