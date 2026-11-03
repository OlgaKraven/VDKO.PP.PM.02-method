param([switch]$Child)
$ErrorActionPreference = 'Stop'
$stand = Get-Content (Join-Path $PSScriptRoot 'stand.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$system = Get-CimInstance Win32_ComputerSystem
$virtual = ($system.Manufacturer -match 'QEMU|innotek|Oracle|VMware|Xen') -or ($system.Model -match 'Virtual Machine|VirtualBox|KVM')
if ($env:COMPUTERNAME -ne $stand.computer -or -not $virtual) {
    throw 'Open PowerShell inside the virtual machine named in stand.json.'
}
if ($Child) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    while ($clock.Elapsed.TotalSeconds -lt 60) {
        for ($n = 1; $n -lt 20000; $n++) { $null = [Math]::Sqrt($n) }
    }
    exit
}
$process = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Child')
Write-Output ('PM02Lab workload PID: ' + $process.Id)
Write-Output 'One CPU thread, automatic stop after 60 seconds. Observe this PID in Task Manager.'
