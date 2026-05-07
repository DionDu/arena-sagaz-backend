param([int]$ParentId = 28364)
Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ParentId -and $_.Name -eq 'python.exe' } | ForEach-Object {
    Write-Host "killing PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
