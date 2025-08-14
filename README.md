## Claude Scheduler (Headless) – Setup and Usage

Automated daily scheduler that keeps Claude CLI active by:
- Waking your system before start time （e.g. 7 a.m.）
- Sending kickoff messages to Claude CLI (This set reset time 5h later)
- Use claude extensively for 2 hours and go for a lunch break, your claude will rest 5 hours after the start time you set in config.yml 
- Monitoring reset times and re-priming automatically
- Managing sleep cycles


### Prerequisites

**Required Tools:**
- Claude CLI
- claude-monitor
- Python 3.10+
- Admin access for system scheduling

**Install claude-monitor:**
```bash
python3 -m pip install claude-monitor
```

**Add to PATH if needed:**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Verify installation:**
```bash
claude --version
claude-monitor --clear | head -n 20
```

### Project Files
- **Main script**: `claude_scheduler.py`
- **Configuration**: `config.yaml`
- **macOS files**: `LaunchAgent.plist`, `run_daemon.sh`
- **Windows files**: `claude_scheduler.bat`, `install_windows_service.ps1`, `windows_task.xml`
- **Wake scripts**: `bin/schedule_wake.sh` (macOS), `bin/schedule_wake.ps1` (Windows)

---

## macOS Setup

### 1) Configure
Edit `config.yaml`:
```yaml
timezone: Europe/London
start_time: "06:00"
sleep_time: "23:00"
weekdays: MTWRFSU
kickoff_prompt: "ping"
use_caffeinate: true
force_sleep_at_quiet_hours: false
```

### 2) Schedule Daily Wake
```bash
chmod +x bin/schedule_wake.sh
sudo bin/schedule_wake.sh
pmset -g sched
```

### 3) Install LaunchAgent
```bash
cp LaunchAgent.plist ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
launchctl load -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
launchctl start com.zidong.claude-scheduler
```

**Monitor logs:**
```bash
tail -f ~/Library/Logs/claude-scheduler.log
```

### Control Commands
```bash
# Stop/Start/Restart
launchctl stop com.zidong.claude-scheduler
launchctl start com.zidong.claude-scheduler

# Uninstall
launchctl unload -w ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist
rm ~/Library/LaunchAgents/com.zidong.claude-scheduler.plist

# Cancel scheduled wakes
sudo pmset repeat cancel
```

---

## Windows Setup

### 1) Configure
Edit `config.yaml`:
```yaml
timezone: America/New_York
start_time: "06:00"
sleep_time: "23:00"
weekdays: MTWRFSU
kickoff_prompt: "ping"
use_caffeinate: true
force_sleep_at_quiet_hours: false
```

### 2) Schedule Wake Task
**Run as Administrator:**
```powershell
bin\schedule_wake.ps1
Get-ScheduledTask -TaskName "ClaudeSchedulerWake"
```

### 3) Install Service
**Run as Administrator:**
```powershell
.\install_windows_service.ps1 -Action install
.\install_windows_service.ps1 -Action start
```

### Control Commands
```powershell
# Status and logs
.\install_windows_service.ps1 -Action status
Get-Content "$env:USERPROFILE\AppData\Local\claude-scheduler.log" -Tail 20

# Stop/Start/Restart
.\install_windows_service.ps1 -Action stop
.\install_windows_service.ps1 -Action start
.\install_windows_service.ps1 -Action restart

# Uninstall
.\install_windows_service.ps1 -Action uninstall
```

### Windows Hibernation & Power Management

**✅ Hibernation Support**: The scheduler works during hibernation through:
- **Wake tasks**: `bin/schedule_wake.ps1` creates wake timers that wake from hibernation
- **Power settings**: Task configured with `AllowStartIfOnBatteries` and `DontStopIfGoingOnBatteries`
- **Auto-restart**: Service restarts automatically after wake-up

**Power behavior**:
- **Active hours**: Prevents system sleep with `powercfg /requestsoverride`
- **Sleep time**: Can force hibernation with `shutdown /h` if `force_sleep_at_quiet_hours: true`
- **Wake reliability**: Enable "Allow wake timers" in Power Options for best results

---

## Quick Test

1. Set `start_time` a few minutes ahead in `config.yaml`

2. **macOS:**
```bash
sudo bin/schedule_wake.sh
launchctl restart com.zidong.claude-scheduler
tail -f ~/Library/Logs/claude-scheduler.log
```

3. **Windows (as Administrator):**
```powershell
bin\schedule_wake.ps1
.\install_windows_service.ps1 -Action restart
Get-Content "$env:USERPROFILE\AppData\Local\claude-scheduler.log" -Tail 20 -Wait
```

Watch for log events: `kickoff`, `monitor_parse`, `sleep_until_reset`

