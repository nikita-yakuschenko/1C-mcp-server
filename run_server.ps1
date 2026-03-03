# Запуск MCP-сервера из корня проекта (одна команда).
# Использование: из D:\1C_mcp выполнить: .\run_server.ps1
# Или из любой папки: & "D:\1C_mcp\run_server.ps1"
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python mcp_server.py
} else {
    python mcp_server.py
}
