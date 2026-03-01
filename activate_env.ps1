# PowerShell script to always activate the virtual environment for this project

# Get the project directory (where this script is located)
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Check if virtual environment exists
if (-not (Test-Path "$ProjectDir\.venv")) {
    Write-Host "Virtual environment not found. Creating..."
    Set-Location $ProjectDir
    python -m venv .venv
    Write-Host "Virtual environment created."
}

# Activate the virtual environment
Write-Host "Activating virtual environment..."
& "$ProjectDir\.venv\Scripts\Activate.ps1"

# Install/update requirements
if (Test-Path "$ProjectDir\requirements.txt") {
    Write-Host "Installing/updating requirements..."
    pip install -r "$ProjectDir\requirements.txt"
}

Write-Host "Virtual environment activated and ready!"
Write-Host "You can now run: streamlit run src/live_conditions_app.py"
