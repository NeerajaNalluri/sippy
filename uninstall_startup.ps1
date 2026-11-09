$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Sippy.lnk'
if (Test-Path $lnk) { Remove-Item $lnk; Write-Host 'Removed Sippy from startup.' } else { Write-Host 'Sippy was not in startup.' }
