[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$path = [IO.Path]::GetFullPath($Executable)
$startup = [Environment]::GetFolderPath('Startup')
$shortcut = Join-Path $startup 'SplatReplay.lnk'
if ($Remove) {
    if (Test-Path -LiteralPath $shortcut) { Remove-Item -LiteralPath $shortcut }
    return
}
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Executable not found.' }
$shell = New-Object -ComObject WScript.Shell
try {
    $link = $shell.CreateShortcut($shortcut)
    $link.TargetPath = $path
    $link.Arguments = '--background'
    $link.WorkingDirectory = Split-Path -Parent $path
    $link.Save()
}
finally { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) }
