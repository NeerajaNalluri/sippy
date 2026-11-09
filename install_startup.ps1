# Makes Sippy start automatically when you log in to Windows
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = (Get-Command pythonw).Source
$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Sippy.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $pythonw
$s.Arguments = '"' + (Join-Path $dir 'sippy.py') + '"'
$s.WorkingDirectory = $dir
$s.Description = 'Sippy - hydration buddy'
$s.Save()
Write-Host "Sippy will now start every time you log in. ($lnk)"
