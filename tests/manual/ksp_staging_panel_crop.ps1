param(
  [Parameter(Mandatory = $true)]
  [string] $InPath,

  [Parameter(Mandatory = $true)]
  [string] $OutPath,

  [int] $X = 0,
  [int] $Y = 0,
  [int] $Width = 240,
  [int] $Height = 0,

  [int] $Scale = 3
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing | Out-Null

if (-not (Test-Path $InPath)) {
  throw "Input not found: $InPath"
}

$src = [System.Drawing.Bitmap]::FromFile($InPath)
try {
  if ($Height -le 0) { $Height = $src.Height - $Y }
  if ($Width -le 0)  { $Width = $src.Width - $X }

  $cropRect = New-Object System.Drawing.Rectangle $X, $Y, $Width, $Height
  $cropped = New-Object System.Drawing.Bitmap $cropRect.Width, $cropRect.Height
  try {
    $g = [System.Drawing.Graphics]::FromImage($cropped)
    try {
      $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
      $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
      $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, $cropRect.Width, $cropRect.Height), $cropRect, [System.Drawing.GraphicsUnit]::Pixel)
    } finally {
      $g.Dispose()
    }

    if ($Scale -gt 1) {
      $scaled = New-Object System.Drawing.Bitmap ($cropRect.Width * $Scale), ($cropRect.Height * $Scale)
      try {
        $g2 = [System.Drawing.Graphics]::FromImage($scaled)
        try {
          $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
          $g2.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
          $g2.DrawImage($cropped, 0, 0, $scaled.Width, $scaled.Height)
        } finally {
          $g2.Dispose()
        }
        $outImg = $scaled
      } catch {
        $scaled.Dispose()
        throw
      }
    } else {
      $outImg = $cropped
    }

    $dir = Split-Path -Parent $OutPath
    if ($dir -and -not (Test-Path $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $outImg.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $OutPath
  } finally {
    if ($cropped) { $cropped.Dispose() }
    if ($scaled) { $scaled.Dispose() }
  }
} finally {
  $src.Dispose()
}

