$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    Write-Error 'Create the environment first: python -m venv .venv, then install requirements.txt.'
}
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
