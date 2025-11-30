# Splat Replay WebView - Build Script
# Generate Windows executable using PyInstaller

Write-Host "Build Start" -ForegroundColor Cyan
Write-Host ""

# 1. Check frontend build
Write-Host "Frontend not built. Starting build..." -ForegroundColor Yellow
Push-Location frontend
npm install
npm run build
Pop-Location
Write-Host "Frontend build completed" -ForegroundColor Green
Write-Host ""

# 2. Cleanup existing build
Write-Host "Cleaning up existing build..." -ForegroundColor Yellow
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}
Write-Host "Cleanup completed" -ForegroundColor Green
Write-Host ""

# 3. Ensure pyinstaller is installed in the project's virtual environment
Write-Host "Installing PyInstaller in project virtual environment..." -ForegroundColor Yellow
uv sync --group build

# 4. Build with PyInstaller from the project's virtual environment
Write-Host ""
Write-Host "Building with PyInstaller..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Gray
Write-Host ""

.\.venv\Scripts\pyinstaller.exe splat-replay-webview.spec --clean

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build succeeded!" -ForegroundColor Green
    
    # 5. Copy config and videos directories
    Write-Host ""
    Write-Host "Copying runtime directories..." -ForegroundColor Yellow
    
    $distDir = "dist\SplatReplay"
    
    # Copy selected config files (do not copy the entire directory)
    if (Test-Path "config") {
        Write-Host "  - Copying selected config files..." -ForegroundColor Gray
        # Ensure destination config directory exists
        New-Item -ItemType Directory -Force -Path "$distDir\config" | Out-Null

        # Copy image_matching.yaml if present
        $srcImageMatching = "config\image_matching.yaml"
        if (Test-Path $srcImageMatching) {
            Copy-Item -Force $srcImageMatching "$distDir\config\image_matching.yaml"
            Write-Host "    - image_matching.yaml copied" -ForegroundColor Gray
        } else {
            Write-Host "    - image_matching.yaml not found, skipping" -ForegroundColor Yellow
        }

        # Copy settings.example.toml as settings.toml if present
        $srcSettingsExample = "config\settings.example.toml"
        if (Test-Path $srcSettingsExample) {
            Copy-Item -Force $srcSettingsExample "$distDir\config\settings.toml"
            Write-Host "    - settings.example.toml copied -> settings.toml" -ForegroundColor Gray
        } else {
            Write-Host "    - settings.example.toml not found, skipping" -ForegroundColor Yellow
        }
    }
    
    # Create empty videos directory structure
    if (-not (Test-Path "$distDir\videos")) {
        Write-Host "  - Creating videos directory..." -ForegroundColor Gray
        New-Item -ItemType Directory -Force -Path "$distDir\videos\recorded" | Out-Null
        New-Item -ItemType Directory -Force -Path "$distDir\videos\edited" | Out-Null
    }
    
    Write-Host "Runtime directories setup completed" -ForegroundColor Green
    
    # Remove ikamodoki1.ttf (redistribution prohibited)
    Write-Host ""
    Write-Host "Removing redistribution-prohibited files..." -ForegroundColor Yellow
    $ikamodokiPaths = @(
        "$distDir\assets\thumbnail\ikamodoki1.ttf",
        "$distDir\_internal\assets\thumbnail\ikamodoki1.ttf"
    )
    foreach ($path in $ikamodokiPaths) {
        if (Test-Path $path) {
            Remove-Item -Force $path
            Write-Host "  - ikamodoki1.ttf removed from: $path" -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host "Executable location:" -ForegroundColor Cyan
    Write-Host "   dist\SplatReplay\SplatReplay.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "How to run:" -ForegroundColor Cyan
    Write-Host "   .\dist\SplatReplay\SplatReplay.exe" -ForegroundColor White
    Write-Host ""
    
    # Display file size
    $exePath = "dist\SplatReplay\SplatReplay.exe"
    if (Test-Path $exePath) {
        $size = (Get-Item $exePath).Length / 1MB
        Write-Host "Executable size: $([math]::Round($size, 2)) MB" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "Build failed" -ForegroundColor Red
    Write-Host "Please check the error details above" -ForegroundColor Yellow
    exit 1
}
