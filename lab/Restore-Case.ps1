$ErrorActionPreference = 'Stop'
$stand = Get-Content (Join-Path $PSScriptRoot 'stand.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$system = Get-CimInstance Win32_ComputerSystem
$virtual = ($system.Manufacturer -match 'QEMU|innotek|Oracle|VMware|Xen') -or ($system.Model -match 'Virtual Machine|VirtualBox|KVM')
if ($env:COMPUTERNAME -ne $stand.computer -or -not $virtual) {
    throw 'Open the virtual machine named in stand.json.'
}
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$approved = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$backup = Join-Path 'C:\PM02' ('case_' + $stand.variant + '\startup-before-' + $sid + '.json')
if (-not (Test-Path $backup)) { throw 'No original startup snapshot for this user and case.' }
$entries = Get-Content $backup -Raw -Encoding UTF8 | ConvertFrom-Json
if ($entries.Count -ne 3 -or @($entries | Where-Object { $_.PSObject.Properties.Name -notcontains 'approved_exists' }).Count) {
    throw 'Retain the existing backup and use the configured snapshot. Original StartupApproved values are missing.'
}
foreach ($entry in $entries) {
    if ($entry.name -notin @('PM02Lab-Report','PM02Lab-Reminder','PM02Lab-Workload')) { throw 'Unexpected backup key.' }
    if ($entry.approved_exists) { $null = [Convert]::FromBase64String($entry.approved_value) }
}
foreach ($entry in $entries) {
    if ($entry.name -notin @('PM02Lab-Report','PM02Lab-Reminder','PM02Lab-Workload')) { throw 'Unexpected backup key.' }
    if ($entry.exists) {
        New-ItemProperty $run -Name $entry.name -PropertyType String -Value $entry.value -Force | Out-Null
    } else {
        Remove-ItemProperty $run -Name $entry.name -ErrorAction SilentlyContinue
    }
    if ($entry.approved_exists) {
        if (-not (Test-Path $approved)) { New-Item $approved -Force | Out-Null }
        New-ItemProperty $approved -Name $entry.name -PropertyType Binary -Value ([Convert]::FromBase64String($entry.approved_value)) -Force | Out-Null
    } elseif (Test-Path $approved) {
        Remove-ItemProperty $approved -Name $entry.name -ErrorAction SilentlyContinue
    }
}
Write-Output 'Original PM02Lab Run and StartupApproved values restored for this Windows user. Event logs were retained.'
