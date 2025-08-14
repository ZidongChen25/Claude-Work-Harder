# PowerShell script to install Claude Scheduler as Windows Service
# Run as Administrator

param(
    [Parameter()]
    [string]$Action = "install",
    
    [Parameter()]
    [string]$ServiceName = "ClaudeScheduler"
)

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchFile = Join-Path $ScriptDir "claude_scheduler.bat"
$TaskName = "ClaudeSchedulerTask"

function Install-ClaudeScheduler {
    Write-Host "Installing Claude Scheduler as Windows Task..." -ForegroundColor Green
    
    # Check if batch file exists
    if (-not (Test-Path $BatchFile)) {
        Write-Error "claude_scheduler.bat not found at: $BatchFile"
        exit 1
    }
    
    # Create a scheduled task that runs at startup and keeps running
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchFile`""
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    
    # Register the task
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
        
        # Configure restart settings using schtasks.exe for better compatibility
        Write-Host "Configuring restart settings..." -ForegroundColor Yellow
        & schtasks.exe /change /tn $TaskName /rl HIGHEST /ri 1 /et 00:00:00 2>$null
        
        Write-Host "Claude Scheduler task installed successfully!" -ForegroundColor Green
        Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
        Write-Host "You can manage it through Task Scheduler or with this script." -ForegroundColor Yellow
    }
    catch {
        Write-Error "Failed to install task: $($_.Exception.Message)"
    }
}

function Uninstall-ClaudeScheduler {
    Write-Host "Uninstalling Claude Scheduler task..." -ForegroundColor Yellow
    
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "Claude Scheduler task uninstalled successfully!" -ForegroundColor Green
    }
    catch {
        Write-Warning "Task not found or already uninstalled: $($_.Exception.Message)"
    }
}

function Start-ClaudeScheduler {
    Write-Host "Starting Claude Scheduler task..." -ForegroundColor Green
    
    try {
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "Claude Scheduler task started!" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to start task: $($_.Exception.Message)"
    }
}

function Stop-ClaudeScheduler {
    Write-Host "Stopping Claude Scheduler task..." -ForegroundColor Yellow
    
    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "Claude Scheduler task stopped!" -ForegroundColor Green
    }
    catch {
        Write-Error "Failed to stop task: $($_.Exception.Message)"
    }
}

function Show-Status {
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        
        Write-Host "Claude Scheduler Status:" -ForegroundColor Cyan
        Write-Host "  State: $($task.State)" -ForegroundColor Yellow
        Write-Host "  Last Run Time: $($info.LastRunTime)" -ForegroundColor Yellow
        Write-Host "  Last Task Result: $($info.LastTaskResult)" -ForegroundColor Yellow
        Write-Host "  Next Run Time: $($info.NextRunTime)" -ForegroundColor Yellow
    }
    catch {
        Write-Warning "Task not found: $($_.Exception.Message)"
    }
}

# Main execution
# Show help without requiring admin privileges
if ($Action.ToLower() -eq "help" -or $Action.ToLower() -eq "--help" -or $Action.ToLower() -eq "-h") {
    Write-Host "Usage: .\install_windows_service.ps1 -Action [install|uninstall|start|stop|restart|status]" -ForegroundColor Cyan
    Write-Host "Example: .\install_windows_service.ps1 -Action install" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Green
    Write-Host "  install   - Install Claude Scheduler as Windows Task"
    Write-Host "  uninstall - Remove Claude Scheduler task"
    Write-Host "  start     - Start the scheduled task"
    Write-Host "  stop      - Stop the scheduled task"
    Write-Host "  restart   - Stop and start the task"
    Write-Host "  status    - Show task status"
    exit 0
}

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator!"
    Write-Host "Try: Right-click PowerShell -> 'Run as Administrator', then run this script" -ForegroundColor Yellow
    exit 1
}

switch ($Action.ToLower()) {
    "install" { Install-ClaudeScheduler }
    "uninstall" { Uninstall-ClaudeScheduler }
    "start" { Start-ClaudeScheduler }
    "stop" { Stop-ClaudeScheduler }
    "status" { Show-Status }
    "restart" { 
        Stop-ClaudeScheduler
        Start-Sleep -Seconds 2
        Start-ClaudeScheduler
    }
    default {
        Write-Host "Unknown action: $Action" -ForegroundColor Red
        Write-Host "Use -Action help for available commands" -ForegroundColor Yellow
    }
}