# Fast-Flux Build Script for Windows
# This script bundles the application into a portable Windows folder.

$FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$BIN_DIR = "./bin"
$FFMPEG_EXE = "$BIN_DIR/ffmpeg.exe"

# 1. Ensure bin directory exists
if (-not (Test-Path $BIN_DIR)) {
    New-Item -ItemType Directory -Path $BIN_DIR
}

# 2. Check for FFmpeg
if (-not (Test-Path $FFMPEG_EXE)) {
    Write-Host "FFmpeg not found in $BIN_DIR. Downloading..." -ForegroundColor Cyan
    
    $tempZip = "ffmpeg_temp.zip"
    Invoke-WebRequest -Uri $FFMPEG_URL -OutFile $tempZip
    
    Write-Host "Extracting FFmpeg..." -ForegroundColor Cyan
    Expand-Archive -Path $tempZip -DestinationPath "ffmpeg_temp" -Force
    
    # Find the ffmpeg.exe in the extracted folder
    $extractedExe = Get-ChildItem -Path "ffmpeg_temp" -Filter "ffmpeg.exe" -Recurse | Select-Object -First 1
    if ($extractedExe) {
        Copy-Item -Path $extractedExe.FullName -Destination $FFMPEG_EXE
        Write-Host "FFmpeg successfully bundled!" -ForegroundColor Green
    } else {
        Write-Error "Could not find ffmpeg.exe in the downloaded archive."
        exit 1
    }
    
    # Cleanup
    Remove-Item -Path $tempZip -Force
    Remove-Item -Path "ffmpeg_temp" -Recurse -Force
} else {
    Write-Host "FFmpeg already present in $BIN_DIR" -ForegroundColor Green
}

# 3. Install build dependencies
Write-Host "Installing build dependencies..." -ForegroundColor Cyan
pip install pyinstaller qasync PyQt6 aiohttp aiofiles

# 4. Run PyInstaller
Write-Host "Building Fast-Flux executable..." -ForegroundColor Cyan
pyinstaller --clean fast_flux.spec

Write-Host "Build complete! Check the 'dist/Fast-Flux' folder." -ForegroundColor Green
Write-Host "You can share the 'Fast-Flux' folder with anyone on Windows." -ForegroundColor Yellow
