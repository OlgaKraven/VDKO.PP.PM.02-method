$ErrorActionPreference = 'Stop'
$stand = Get-Content (Join-Path $PSScriptRoot 'stand.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$system = Get-CimInstance Win32_ComputerSystem
$virtual = ($system.Manufacturer -match 'QEMU|innotek|Oracle|VMware|Xen') -or ($system.Model -match 'Virtual Machine|VirtualBox|KVM')
if ($env:COMPUTERNAME -ne $stand.computer -or -not $virtual) {
    throw 'Open the virtual machine named in stand.json. The main computer is not a lab target.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open Windows PowerShell as administrator inside the lab VM.'
}
$case = Join-Path 'C:\PM02' ('case_' + $stand.variant)
New-Item $case -ItemType Directory -Force | Out-Null
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$approved = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'
if (-not (Test-Path $run)) { New-Item $run -Force | Out-Null }
$names = @('PM02Lab-Report','PM02Lab-Reminder','PM02Lab-Workload')
$backup = Join-Path $case ('startup-before-' + $identity.User.Value + '.json')
if (-not (Test-Path $backup)) {
    $before = foreach ($name in $names) {
        $key = Get-Item $run
        $approvalKey = Get-Item $approved -ErrorAction SilentlyContinue
        $approvalExists = $approvalKey -and ($approvalKey.GetValueNames() -contains $name)
        $approvalValue = if ($approvalExists) { [Convert]::ToBase64String([byte[]]$approvalKey.GetValue($name)) } else { $null }
        @{name=$name; exists=($key.GetValueNames() -contains $name); value=$key.GetValue($name);
          approved_exists=[bool]$approvalExists; approved_value=$approvalValue}
    }
    @($before) | ConvertTo-Json -Depth 4 | Set-Content $backup -Encoding UTF8
}
$saved = Get-Content $backup -Raw -Encoding UTF8 | ConvertFrom-Json
if ($saved.Count -ne 3 -or @($saved | Where-Object { $_.PSObject.Properties.Name -notcontains 'approved_exists' }).Count) {
    throw 'Retain the existing startup backup. This case requires a backup that also records StartupApproved; use the configured snapshot for a fresh case.'
}
Set-Content (Join-Path $case 'report-note.txt') -Encoding UTF8 -Value ('PM02Lab training report viewer: ' + $stand.subject)
Set-Content (Join-Path $case 'reminder.txt') -Encoding UTF8 -Value 'PM02Lab training reminder. This is not a system or security component.'
Set-Content (Join-Path $case 'Report.cmd') -Encoding ASCII -Value ('@start "" notepad.exe "' + $case + '\report-note.txt"')
Set-Content (Join-Path $case 'Reminder.cmd') -Encoding ASCII -Value ('@start "" notepad.exe "' + $case + '\reminder.txt"')
$work = '@powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'Start-Workload.ps1') + '" -Child'
Set-Content (Join-Path $case 'Workload.cmd') -Encoding ASCII -Value $work
foreach ($part in @('Report','Reminder','Workload')) {
    New-ItemProperty $run -Name ('PM02Lab-' + $part) -PropertyType String -Force -Value ('cmd.exe /c "' + $case + '\' + $part + '.cmd"') | Out-Null
}
if (-not [Diagnostics.EventLog]::SourceExists('PM02Lab')) {
    New-EventLog -LogName Application -Source 'PM02Lab'
}
$messages = @(
    'TRAINING DOSSIER, not a spontaneous OS failure. Check the client connection profile against the stand passport.',
    'TRAINING DOSSIER, not a spontaneous OS failure. SELECT is allowed for client03; modifying table data is not allowed.',
    'TRAINING DOSSIER, not a spontaneous OS failure. Assess the three PM02Lab startup entries and the bounded workload.')
for ($i=0; $i -lt $messages.Count; $i++) {
    Write-EventLog -LogName Application -Source PM02Lab -EventId (1101 + $i) -EntryType Error -Message $messages[$i]
}
Write-Output ('Prepared training case for ' + $stand.computer + ' / ' + $stand.subject)
Write-Output 'Created three PM02Lab training startup entries and three explicitly labelled training events.'
Write-Output ('Original startup values retained at ' + $backup)
