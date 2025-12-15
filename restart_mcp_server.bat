@echo off
setlocal

cd /d "%~dp0"

echo [GeePT MCP] Stopping any running server processes...
powershell -NoProfile -Command ^
  "$pids = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'mcp_server\.main') } | Select-Object -ExpandProperty ProcessId; " ^
  "if ($pids) { $pids | ForEach-Object { Write-Host ('[GeePT MCP] Killing PID ' + $_); try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} } } else { Write-Host '[GeePT MCP] No existing server found.' }"

echo [GeePT MCP] Starting MCP server...
where uv >nul 2>nul
if %errorlevel%==0 (
  uv run -m mcp_server.main %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 (
  python -m mcp_server.main %*
  exit /b %errorlevel%
)

echo [GeePT MCP] ERROR: Neither "uv" nor "python" was found on PATH.
exit /b 1

