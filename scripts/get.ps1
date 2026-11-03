# Indian Stock Analyst - one-line installer / updater for Windows 10/11.
#
#   Open PowerShell (Start menu -> type "PowerShell" -> Enter) and paste:
#     irm https://raw.githubusercontent.com/n00bsniper2024/Indian_stock_Analyst/main/scripts/get.ps1 | iex
#
# What it does (no admin rights needed, nothing outside your user folder):
#   1. downloads the latest code into  %LOCALAPPDATA%\IndianStockAnalyst
#   2. installs "uv" (a small Python manager from astral.sh) if you don't have it; uv downloads its own Python 3.12,
#      so you do NOT need to install Python yourself and an existing Python is left untouched
#   3. installs the app's libraries into a private folder (.venv) inside the app folder
#   4. puts "Indian Stock Analyst" on your Desktop and in the Start menu, then opens the dashboard
# Run the same line again any time to update. Your saved API keys (.env) and cached data are kept.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is much faster without the progress bar

$Repo   = 'n00bsniper2024/Indian_stock_Analyst'
$Branch = if ($env:ISA_BRANCH) { $env:ISA_BRANCH } else { 'main' }
$Dir    = if ($env:ISA_HOME) { $env:ISA_HOME } else { Join-Path $env:LOCALAPPDATA 'IndianStockAnalyst' }

function Step($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }

Step "Getting the latest Indian Stock Analyst ($Branch)"
if ($env:ISA_SOURCE_DIR) { $src = $env:ISA_SOURCE_DIR } else {
    $tmp = Join-Path $env:TEMP ("isa-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'src.zip'
    Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $tmp
    $src = (Get-ChildItem -Path $tmp -Directory | Select-Object -First 1).FullName
}
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
if ((Resolve-Path $src).Path.TrimEnd('\') -ne (Resolve-Path $Dir).Path.TrimEnd('\')) {
    # copy the code, keeping the user's keys (.env), cache and environment
    robocopy $src $Dir /E /XD .git .venv .cache .pytest_cache __pycache__ /XF .env /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copying files failed (robocopy code $LASTEXITCODE)" }
    $global:LASTEXITCODE = 0
}

Step "Checking for uv (Python manager)"
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) {
    $cand = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
    if (Test-Path $cand) { $uv = $cand } else {
        Write-Host "Installing uv from astral.sh ..."
        powershell -NoProfile -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $uv = $cand
        if (-not (Test-Path $uv)) { throw "uv did not install. See https://docs.astral.sh/uv/getting-started/installation/" }
    }
}

Step "Installing Python 3.12 and the app's libraries (first time: a few minutes)"
$py = Join-Path $Dir '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { & $uv venv --python 3.12 (Join-Path $Dir '.venv'); if ($LASTEXITCODE) { throw "Creating the environment failed" } }
& $uv pip install --python $py -r (Join-Path $Dir 'requirements.txt')
if ($LASTEXITCODE) { throw "Installing libraries failed" }
$envFile = Join-Path $Dir '.env'
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $Dir '.env.example') $envFile }

Step "Creating shortcuts"
$start = Join-Path $Dir 'scripts\start-windows.bat'
$shell = New-Object -ComObject WScript.Shell
$places = @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('Programs')) ''))
foreach ($p in $places) {
    if (-not $p -or -not (Test-Path $p)) { continue }
    $lnk = $shell.CreateShortcut((Join-Path $p 'Indian Stock Analyst.lnk'))
    $lnk.TargetPath = $start
    $lnk.WorkingDirectory = $Dir
    $ico = Join-Path $Dir 'docs\icon.ico'
    if (Test-Path $ico) { $lnk.IconLocation = $ico }
    $lnk.Description = 'Indian Stock Analyst dashboard'
    $lnk.Save()
}

Write-Host "`nInstalled in $Dir" -ForegroundColor Green
Write-Host "Open it any time from the 'Indian Stock Analyst' icon on your Desktop or in the Start menu."
if (-not $env:ISA_NO_LAUNCH) {
    Step "Starting the dashboard (a black window opens; keep it open while you use the dashboard)"
    Start-Process -FilePath $start -WorkingDirectory $Dir
}
