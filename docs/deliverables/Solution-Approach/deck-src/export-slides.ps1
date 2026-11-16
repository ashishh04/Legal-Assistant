param(
  [Parameter(Mandatory = $true)][string]$Deck,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [int]$Width = 1600,
  [string]$Only = ""
)
# Export each slide of a deck to PNG with PowerPoint, without closing any
# presentation the user already has open.
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force $OutDir | Out-Null
$ppt = New-Object -ComObject PowerPoint.Application
$hadOpen = $ppt.Presentations.Count
$pres = $ppt.Presentations.Open($Deck, -1, 0, 0)   # ReadOnly, not Untitled, no window
try {
  $w = $pres.PageSetup.SlideWidth; $h = $pres.PageSetup.SlideHeight
  $height = [int]([math]::Round($Width * $h / $w))
  $wanted = @()
  if ($Only -ne "") { $wanted = $Only.Split(",") | ForEach-Object { [int]$_ } }
  for ($i = 1; $i -le $pres.Slides.Count; $i++) {
    if ($wanted.Count -gt 0 -and -not ($wanted -contains $i)) { continue }
    $file = Join-Path $OutDir ("slide-{0:D2}.png" -f $i)
    $pres.Slides.Item($i).Export($file, "PNG", $Width, $height)
  }
  "slides: $($pres.Slides.Count)  size: $w x $h pt"
} finally {
  $pres.Close()
  if ($hadOpen -eq 0 -and $ppt.Presentations.Count -eq 0) { $ppt.Quit() }
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt)
}
