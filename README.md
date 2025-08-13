## Claude Scheduler (Headless) – Setup and Usage

This project runs a daily headless scheduler that:
- Wakes your Mac shortly before a configured start time
- Sends a tiny kickoff message to Claude CLI
- Reads the next reset from claude-monitor
- Sleeps until that reset and “re-primes” (sends the tiny message again)
- Repeats until sleep time, then optionally forces system sleep

It runs as a macOS LaunchAgent and logs to `~/Library/Logs/claude-scheduler.log`.

### Prerequisites
- macOS with admin access (for `pmset`)
- Installed tools:
  - Claude CLI
  - claude-monitor
  - Python 3.10+ (no extra Python packages required)

Note: You can use a virtualenv/conda if you prefer, but LaunchAgent `ProgramArguments` points to `/usr/bin/python3`. For simplicity and reliability with LaunchAgent, using the system Python is recommended. If you must use venv/conda, adjust the LaunchAgent to call that interpreter path.

- Install claude-monitor (from PyPI) if missing:
```bash
python3 -m pip install claude-monitor
```
- If the command isn’t found after install, add user-local bin to PATH (macOS uses zsh by default):
```bash
# zsh (default on modern macOS)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
# or Bash users:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```
Verify:
```bash
which claude-monitor
claude-monitor --clear | head -n 50 | cat
```

Confirm CLI tools:
```bash
claude --version
claude doctor | cat
claude -p "ping" --model claude-3-7-sonnet --output-format json | cat
claude-monitor --clear | head -n 50 | cat
```

### Files
- Daemon: `/Users/zidong/Desktop/claude_timer/claude_scheduler.py`
- Config: `/Users/zidong/Desktop/claude_timer/config.yaml`
- LaunchAgent template: `/Users/zidong/Desktop/claude_timer/LaunchAgent.plist`
- Wake helper: `/Users/zidong/Desktop/claude_timer/bin/schedule_wake.sh`
- Logs: `~/Library/Logs/claude-scheduler.log`

### 1) Configure
Edit `/Users/zidong/Desktop/claude_timer/config.yaml`:
```yaml
timezone: Europe/London
start_time: "06:00"
sleep_time: "23:00"
weekdays: MTWRFSU
model: claude-3-7-sonnet
kickoff_prompt: "ping"
use_caffeinate: true
force_sleep_at_quiet_hours: false
```
Notes:
- `weekdays`: use `MTWRFSU`, `weekdays`, or any subset (e.g., `MTWRF`).
- `use_caffeinate: true` avoids idle sleep while the daemon is active.
- `force_sleep_at_quiet_hours: false` leaves the system awake at sleep_time; if `true`, the daemon calls `pmset sleepnow` (requires scheduled wake to be set!).

### 2) Schedule Daily Wake (one-time)
Wake ~2 minutes before `start_time` every active day. The helper prints the command; run it with sudo.
```bash
chmod +x /Users/zidong/Desktop/claude_timer/bin/schedule_wake.sh
sudo /Users/zidong/Desktop/claude_timer/bin/schedule_wake.sh
pmset -g sched
```
To change times later, update `config.yaml` and re-run the script with sudo.

### 3) Install LaunchAgent
Copy the LaunchAgent into your user LaunchAgents and load it:
```bash
cp /Users/zidong/Desktop/claude_timer/LaunchAgent.plist \
   ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
launchctl load -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
```
Start immediately (optional):
```bash
launchctl start com.zidong.claude-scheduler
```
Check it’s running (tail the log):
```bash
tail -f ~/Library/Logs/claude-scheduler.log
```

### 4) How it works daily
- At `start_time`: the Mac should wake (per `pmset repeat`), the daemon sends a kickoff ping, parses claude-monitor for the current block reset, then sleeps until reset (+ ~3s buffer) and re-primes. It loops until `sleep_time`.
- At `sleep_time`: if `force_sleep_at_quiet_hours: true`, the daemon triggers `pmset sleepnow`. Otherwise, it idles until the next day.
- The daemon auto-restarts if it crashes or after reboots/logins.

### Lid and Power Behavior
- Most reliable always-on operation: clamshell mode (AC power + external display + keyboard/mouse) or keep lid open. `caffeinate` prevents idle sleep but not lid-close sleep.
- If you rely on automatic wake from sleep, verify with:
```bash
pmset -g sched | cat
```

### Operations
- Stop the agent:
```bash
launchctl stop com.zidong.claude-scheduler
```
- Start the agent:
```bash
launchctl start com.zidong.claude-scheduler
```
- Unload and remove:
```bash
launchctl unload -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
rm ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
```
- Cancel all scheduled wakes:
```bash
sudo pmset repeat cancel
pmset -g sched
```

### Troubleshooting
- No kickoff at start_time:
  - Verify scheduled wake: `pmset -g sched`
  - Confirm AC power; some Macs won’t wake on battery.
  - Check log: `tail -n 200 ~/Library/Logs/claude-scheduler.log`
- claude-monitor parse fails:
  - Run: `claude-monitor --clear | head -n 80 | cat`
  - The daemon falls back to now+5h and retries with backoff; check log entries `monitor_parse`.
- Permissions / PATH:
  - The LaunchAgent sets PATH to `/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin`. Ensure `claude` and `claude-monitor` live in one of these.

### Quick Test (same day)
- Temporarily set `start_time` a few minutes ahead of now in `config.yaml`.
- Re-run wake script (if you want a scheduled wake):
```bash
sudo /Users/zidong/Desktop/claude_timer/bin/schedule_wake.sh
```
- Restart agent to reload config:
```bash
launchctl stop com.zidong.claude-scheduler
launchctl start com.zidong.claude-scheduler
```
- Watch the log for `kickoff`, `monitor_parse`, `sleep_until_reset`, and the next primer send.

