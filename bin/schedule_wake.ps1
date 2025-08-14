# PowerShell script to schedule Windows wake times
# Equivalent of schedule_wake.sh for Windows
# Requires Administrator privileges

param(
    [Parameter()]
    [string]$ConfigPath = ""
)

# Function to read config.yaml
function Read-Config {
    param([string]$Path)
    
    if (-not (Test-Path $Path)) {
        Write-Error "Config file not found: $Path"
        return $null
    }
    
    $content = Get-Content $Path -Raw
    $startTime = if ($content -match 'start_time:\s*"?([0-9]{1,2}:[0-9]{2})"?') { $matches[1] } else { "06:00" }
    $weekdays = if ($content -match 'weekdays:\s*([A-Za-z]+)') { $matches[1] } else { "MTWRFSU" }
    
    return @{
        StartTime = $startTime
        Weekdays = $weekdays
    }
}

# Function to convert weekday string to Windows format
function Convert-WeekdayString {
    param([string]$WeekdayStr)
    
    $days = @()
    $dayMap = @{
        'M' = 'MON'
        'T' = 'TUE' 
        'W' = 'WED'
        'R' = 'THU'  # Thursday
        'F' = 'FRI'
        'S' = 'SAT'
        'U' = 'SUN'
    }
    
    if ($WeekdayStr -eq "WEEKDAYS") {
        return "MON TUE WED THU FRI"
    }
    
    foreach ($char in $WeekdayStr.ToCharArray()) {
        if ($dayMap.ContainsKey($char)) {
            $days += $dayMap[$char]
        }
    }
    
    return $days -join " "
}

# Function to calculate wake time (2 minutes before start time)
function Get-WakeTime {
    param([string]$StartTime)
    
    $parts = $StartTime -split ":"
    $hour = [int]$parts[0]
    $minute = [int]$parts[1]
    
    # Subtract 2 minutes
    $minute -= 2
    if ($minute -lt 0) {
        $minute += 60
        $hour -= 1
        if ($hour -lt 0) {
            $hour = 23
        }
    }
    
    return "{0:D2}:{1:D2}:00" -f $hour, $minute
}

# Main execution
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator!"
    exit 1
}

# Get script directory and config path
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $RootDir "config.yaml"
}

Write-Host "Reading configuration from: $ConfigPath" -ForegroundColor Cyan

# Read configuration
$config = Read-Config -Path $ConfigPath
if (-not $config) {
    exit 1
}

Write-Host "Start time: $($config.StartTime)" -ForegroundColor Yellow
Write-Host "Weekdays: $($config.Weekdays)" -ForegroundColor Yellow

# Calculate wake time and convert weekdays
$wakeTime = Get-WakeTime -StartTime $config.StartTime
$windowsDays = Convert-WeekdayString -WeekdayStr $config.Weekdays

Write-Host "Wake time (2 min before): $wakeTime" -ForegroundColor Green
Write-Host "Windows days format: $windowsDays" -ForegroundColor Green

# Clear any existing wake timers
Write-Host "Clearing existing wake timers..." -ForegroundColor Yellow
try {
    powercfg /waketimers
    $existingTimers = powercfg /waketimers 2>&1
    Write-Host "Current wake timers:" -ForegroundColor Cyan
    Write-Host $existingTimers -ForegroundColor Gray
}
catch {
    Write-Warning "Could not check existing wake timers: $($_.Exception.Message)"
}

# Note: Windows doesn't have a direct equivalent to macOS pmset repeat
# Instead, we'll use Task Scheduler to create a wake task
Write-Host "`nCreating Windows wake task..." -ForegroundColor Green

$taskName = "ClaudeSchedulerWake"
$wakeAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -Command `"Write-Host 'Claude Scheduler Wake Task'`""

# Create triggers for each day
$triggers = @()
foreach ($day in $windowsDays -split " ") {
    $dayNumber = switch ($day) {
        "MON" { 2 }
        "TUE" { 3 }
        "WED" { 4 }
        "THU" { 5 }
        "FRI" { 6 }
        "SAT" { 7 }
        "SUN" { 1 }
    }
    
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $day -At $wakeTime
    $triggers += $trigger
}

$settings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

try {
    # Remove existing task if it exists
    try {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    } catch {}
    
    # Register new task
    Register-ScheduledTask -TaskName $taskName -Action $wakeAction -Trigger $triggers -Settings $settings -Principal $principal -Force
    
    Write-Host "Wake task '$taskName' created successfully!" -ForegroundColor Green
    Write-Host "The system will attempt to wake at $wakeTime on: $windowsDays" -ForegroundColor Yellow
    Write-Host "`nNote: Windows wake functionality depends on:" -ForegroundColor Cyan
    Write-Host "  - Power settings allowing wake timers" -ForegroundColor Gray
    Write-Host "  - Hardware support for scheduled wake" -ForegroundColor Gray
    Write-Host "  - System being in sleep/hibernate mode" -ForegroundColor Gray
    
    # Show current power settings
    Write-Host "`nCurrent power settings:" -ForegroundColor Cyan
    powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYWAKETIMERS | Select-String -Pattern "Current AC Power Setting Index|Current DC Power Setting Index"
}
catch {
    Write-Error "Failed to create wake task: $($_.Exception.Message)"
    exit 1
}

Write-Host "`nTo verify the task was created, run: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Yellow