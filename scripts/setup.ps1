Write-Host "🔹 Creating virtual environment using uv..."
uv venv .venv

Write-Host "🔹 Activating virtual environment..."
. .\.venv\Scripts\Activate.ps1

Write-Host "🔹 Installing dependencies from pyproject.toml..."
uv pip install -r pyproject.toml

Write-Host "✅ Setup completed successfully"
Write-Host "👉 Activate env using: .\.venv\Scripts\Activate.ps1"
