<#
.SYNOPSIS
  Copies the demo case documents into the OneDrive-synced SharePoint "Cases" library, into the
  folder each document's library_path names: /sites/Legal/Cases/<Country>/<Case>/<File>.

.DESCRIPTION
  1. In SharePoint, open the Legal site > Cases library and select Sync. OneDrive creates a local
     folder, usually C:\Users\<you>\<Organisation name>\Legal - Cases.
  2. Run this script with that folder as -SyncedLibrary. OneDrive then uploads the copies.

  Works with either catalogue:
  - the pack's csv\fact_document.csv (default): uploads the 12 sample documents (sample_file = True);
  - documents_150_meta\manifest.csv: uploads every file it lists (column "file" = name in -SourceDir).

  Files are placed by library_path, never by file name. The 60 "Contoso" files in documents\ are in
  neither catalogue, so they are never uploaded.

.EXAMPLE
  .\upload_to_sharepoint.ps1 -SyncedLibrary "$env:USERPROFILE\Contoso\Legal - Cases" -WhatIf

.EXAMPLE
  .\upload_to_sharepoint.ps1 -SyncedLibrary "$env:USERPROFILE\Contoso\Legal - Cases" `
      -Catalogue <path>\documents_150_meta\manifest.csv -SourceDir <path>\documents_150
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)] [string] $SyncedLibrary,
    [string] $Catalogue = (Join-Path $PSScriptRoot '..\..\docs\Ferrero_Demo_Pack\csv\fact_document.csv'),
    [string] $SourceDir = (Join-Path $PSScriptRoot '..\..\docs\Ferrero_Demo_Pack\documents'),
    [string] $LibraryRoot = '/sites/Legal/Cases/'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SyncedLibrary -PathType Container)) {
    throw "Synced library folder not found: $SyncedLibrary (select Sync on the Cases library first)."
}

$rows = @(Import-Csv -LiteralPath $Catalogue -Encoding UTF8)
if ($rows.Count -eq 0) { throw "No rows in $Catalogue." }
$columns = @($rows[0].PSObject.Properties.Name)
$manifestMode = $columns -contains 'file'

$count = 0
$skipped = 0
$missing = @()
foreach ($row in $rows) {
    if (-not $manifestMode -and ($columns -contains 'sample_file') -and $row.sample_file -ne 'True') { continue }
    $name = if ($manifestMode) { $row.file } else { $row.title }
    $path = $row.library_path
    if (-not $path -or -not $path.StartsWith($LibraryRoot)) {
        Write-Warning "Skipping $name - library_path is not under $LibraryRoot : $path"
        $skipped++
        continue
    }
    $source = Join-Path $SourceDir $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        $missing += $name
        continue
    }
    $target = Join-Path $SyncedLibrary ($path.Substring($LibraryRoot.Length) -replace '/', '\')
    if ($PSCmdlet.ShouldProcess($target, "Copy $name")) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
    $count++
}

$verb = if ($WhatIfPreference) { 'Would copy' } else { 'Copied' }
Write-Host "$verb $count file(s) into $SyncedLibrary; skipped $skipped."
if ($missing.Count -gt 0) {
    Write-Warning ("{0} catalogue file(s) not found in {1}: {2}" -f $missing.Count, $SourceDir, ($missing -join ', '))
}
if (-not $WhatIfPreference) {
    Write-Host 'OneDrive uploads them in the background. Wait until every file shows a green tick before testing the agent.'
}
