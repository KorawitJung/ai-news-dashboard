<#
  Registers Windows scheduled tasks for AI Daily (current user, no admin needed).

    .\install_morning_task.ps1                  # fetch news every day at 07:00
    .\install_morning_task.ps1 -Time 06:30      # pick another time
    .\install_morning_task.ps1 -StartAtLogon    # also start the dashboard server when you sign in
    .\install_morning_task.ps1 -Uninstall       # remove both tasks

  If the PC is off or asleep at the set time, Windows runs the fetch as soon as it can.
#>
param(
  [string]$Time = "07:00",
  [switch]$StartAtLogon,
  [switch]$Uninstall
)

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $dir ".venv\Scripts\pythonw.exe"
$fetchTask = "AI Daily - morning news fetch"
$serverTask = "AI Daily - dashboard server"

if ($Uninstall) {
  foreach ($t in @($fetchTask, $serverTask)) {
    Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
  }
  Write-Host "Removed AI Daily scheduled tasks."
  return
}

if (-not (Test-Path $pythonw)) {
  Write-Error "Virtual environment not found. Run start_dashboard.bat once first."
  exit 1
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
$fetch = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$dir\update_news.py`"" -WorkingDirectory $dir
$daily = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact($Time, "HH:mm", $null))
Register-ScheduledTask -TaskName $fetchTask -Action $fetch -Trigger $daily -Settings $settings -Description "Fetches AI news for the AI Daily dashboard." -Force | Out-Null
Write-Host "Scheduled daily news fetch at $Time  ('$fetchTask')"

if ($StartAtLogon) {
  $serverSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0
  $serve = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$dir\app.py`"" -WorkingDirectory $dir
  $logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
  Register-ScheduledTask -TaskName $serverTask -Action $serve -Trigger $logon -Settings $serverSettings -Description "Runs the AI Daily dashboard at http://127.0.0.1:5050" -Force | Out-Null
  Write-Host "Dashboard server will start when you sign in  ('$serverTask')"
}
