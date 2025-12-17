param(
  [Parameter(Mandatory = $true)]
  [string] $OutPath,

  [string] $TitleLike = "*Kerbal Space Program*"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing | Out-Null

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class Win32 {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }

  [DllImport("user32.dll")]
  public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern bool SetWindowPos(
    IntPtr hWnd,
    IntPtr hWndInsertAfter,
    int X,
    int Y,
    int cx,
    int cy,
    uint uFlags
  );

  public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
  public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);

  public const uint SWP_NOSIZE = 0x0001;
  public const uint SWP_NOMOVE = 0x0002;
  public const uint SWP_SHOWWINDOW = 0x0040;
}
"@ | Out-Null

function Get-KspProcess {
  $p = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like $TitleLike } | Select-Object -First 1
  if ($p) { return $p }

  $p = Get-Process -Name "KSP_x64" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  if ($p) { return $p }

  $p = Get-Process -Name "KSP" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
  return $p
}

$proc = Get-KspProcess
if (-not $proc) {
  throw "Could not find a KSP window (title like '$TitleLike')."
}

$hWnd = $proc.MainWindowHandle

# Restore + focus window so screen capture hits the right pixels.
[void][Win32]::ShowWindow($hWnd, 9)           # SW_RESTORE
[void][Win32]::SetForegroundWindow($hWnd)
[void][Win32]::SetWindowPos(
  $hWnd,
  [Win32]::HWND_TOPMOST,
  0, 0, 0, 0,
  ([Win32]::SWP_NOMOVE -bor [Win32]::SWP_NOSIZE -bor [Win32]::SWP_SHOWWINDOW)
)
Start-Sleep -Milliseconds 250

$rect = New-Object Win32+RECT
if (-not [Win32]::GetWindowRect($hWnd, [ref]$rect)) {
  throw "GetWindowRect failed."
}

$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) {
  throw "Invalid window rect: $($rect.Left),$($rect.Top),$($rect.Right),$($rect.Bottom)"
}

$bmp = New-Object System.Drawing.Bitmap $width, $height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)

$dir = Split-Path -Parent $OutPath
if ($dir -and -not (Test-Path $dir)) {
  New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$gfx.Dispose()
$bmp.Dispose()

[void][Win32]::SetWindowPos(
  $hWnd,
  [Win32]::HWND_NOTOPMOST,
  0, 0, 0, 0,
  ([Win32]::SWP_NOMOVE -bor [Win32]::SWP_NOSIZE -bor [Win32]::SWP_SHOWWINDOW)
)

Write-Output $OutPath
