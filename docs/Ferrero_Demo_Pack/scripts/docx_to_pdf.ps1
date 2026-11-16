<#
  Convert every .docx in -InDir to PDF in -OutDir with Microsoft Word (SaveAs2, wdFormatPDF).
  Word shapes Arabic right-to-left correctly and its PDFs extract in logical order.
  One Word instance is reused for the batch. Files that already have a PDF are skipped,
  so the script can be re-run after an interruption.
  (ExportAsFixedFormat is deliberately not used: on this machine it hangs behind the
  classification add-in, while SaveAs2 completes in ~2 s per document.)
  Usage: powershell -ExecutionPolicy Bypass -File docx_to_pdf.ps1 -InDir <dir> -OutDir <dir>
#>
param(
    [Parameter(Mandatory = $true)][string]$InDir,
    [Parameter(Mandatory = $true)][string]$OutDir
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$files = Get-ChildItem -LiteralPath $InDir -Filter *.docx -File | Sort-Object Name |
    Where-Object { -not (Test-Path -LiteralPath (Join-Path $OutDir ([IO.Path]::ChangeExtension($_.Name, '.pdf')))) }
if (-not $files) { Write-Output "Nothing to convert in $InDir"; exit 0 }

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0          # wdAlertsNone
$ok = 0; $failed = @()
try {
    foreach ($f in $files) {
        [string]$pdf = Join-Path $OutDir ([IO.Path]::ChangeExtension($f.Name, '.pdf'))
        [int]$fmt = 17                                                         # wdFormatPDF
        $doc = $null
        try {
            $doc = $word.Documents.Open([string]$f.FullName, $false, $true, $false)   # FileName, ConfirmConversions, ReadOnly, AddToRecentFiles
            $doc.SaveAs2([ref]$pdf, [ref]$fmt)
            $ok++
        } catch {
            $failed += "$($f.Name): $($_.Exception.Message)"
        } finally {
            if ($doc) { $doc.Close(0) | Out-Null; [void][Runtime.InteropServices.Marshal]::ReleaseComObject($doc) }
        }
    }
} finally {
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
Write-Output "Converted $ok of $($files.Count) to $OutDir"
if ($failed) { Write-Output "FAILED:"; $failed | ForEach-Object { Write-Output "  $_" }; exit 1 }
