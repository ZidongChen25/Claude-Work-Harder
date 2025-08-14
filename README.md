## Claude Scheduler (Headless) – Setup and Usage

Automated daily scheduler that keeps Claude CLI active by:
- Waking your system before start time （e.g. 7 a.m.）
- Sending kickoff messages to Claude CLI (This set reset time 5h later)
- Use claude extensively for 2 hours and go for a lunch break, your claude will reset 5 hours after the start time you set in config.yml 
- Monitoring reset times and re-priming automatically
- Managing sleep cycles


### Prerequisites

**Required (install in this order):**

1. **Python 3.10+** with pip
2. **Claude CLI**: [Install via npm (official)](https://www.npmjs.com/package/@anthropics/claude)
3. **claude-monitor**: [Install via PyPI (official)](https://pypi.org/project/claude-monitor/)

**Verify installation:**
```bash
claude --version
claude-monitor --clear | head -n 5
```

**Note**: The scheduler automatically handles path issues on Windows scheduled tasks.

### Project Files
- **Main script**: `claude_scheduler.py`
- **Configuration**: `config.yaml`
- **macOS files**: `LaunchAgent.plist`, `run_daemon.sh`
- **Windows files**: `claude_scheduler.bat`, `install_windows_service.ps1`, `windows_task.xml`
- **Wake scripts**: `bin/schedule_wake.sh` (macOS), `bin/schedule_wake.ps1` (Windows)

---

## macOS Setup

### 1) Configure  
Edit `config.yaml` (example):
```yaml
timezone: Europe/London
start_time: "06:00"
sleep_time: "23:00"
weekdays: MTWRFSU
kickoff_prompt: "ping"
```

### 2) Install
```bash
# Install wake schedule and LaunchAgent
chmod +x bin/schedule_wake.sh
sudo bin/schedule_wake.sh
cp LaunchAgent.plist ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
launchctl load -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
launchctl start com.zidong.claude-scheduler
```

### 3) Monitor
```bash
# View logs  
tail -f ~/Library/Logs/claude-scheduler.log

# Control service
launchctl stop/start com.zidong.claude-scheduler
launchctl unload -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
```

---

## Windows Setup

### 1) Configure
Edit `config.yaml` (example):
```yaml
timezone: America/New_York
start_time: "06:00"
sleep_time: "23:00"
weekdays: MTWRFSU
kickoff_prompt: "ping"
```

### 2) Install (Run PowerShell as Administrator)
```powershell
# Install wake task and service
bin\schedule_wake.ps1
.\install_windows_service.ps1 -Action install
.\install_windows_service.ps1 -Action start

# Verify
.\install_windows_service.ps1 -Action status
```

### 3) Monitor
```powershell
# View logs
Get-Content "$env:USERPROFILE\AppData\Local\claude-scheduler.log" -Tail 20 -Wait

# Control service
.\install_windows_service.ps1 -Action stop/start/restart/uninstall
```

**✅ Hibernation Compatible**: Automatically wakes from hibernation and resumes operation.

---

## Troubleshooting

**Check logs first:**
```powershell
Get-Content "$env:USERPROFILE\AppData\Local\claude-scheduler.log" -Tail 20 -Wait
```


## Quick Test

1. Set `start_time` a few minutes ahead in `config.yaml`
2. Restart the scheduler service 
3. Watch logs for: `kickoff`, `send_claude` (rc: 0), `monitor_parse`

**Windows:**
```powershell
.\install_windows_service.ps1 -Action restart
Get-Content "$env:USERPROFILE\AppData\Local\claude-scheduler.log" -Tail 10 -Wait
```

**macOS:**
```bash
launchctl restart com.zidong.claude-scheduler
tail -f ~/Library/Logs/claude-scheduler.log
```

