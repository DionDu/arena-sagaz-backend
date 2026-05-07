Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|py' } | Select-Object ProcessId,ParentProcessId,Name | Format-Table -AutoSize
