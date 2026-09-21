[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SdkRoot,
    [Parameter(Mandatory = $true)][string]$JavaHome,
    [string]$BuildToolsVersion = '35.0.0',
    [int]$Platform = 35
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$sdk = [IO.Path]::GetFullPath($SdkRoot)
$jdk = [IO.Path]::GetFullPath($JavaHome)
$tools = Join-Path $sdk "build-tools\$BuildToolsVersion"
$androidJar = Join-Path $sdk "platforms\android-$Platform\android.jar"
function Invoke-Native {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Native command failed ($LASTEXITCODE): $Executable" }
}
$build = Join-Path $repo ('.tmp\android-build-' + [guid]::NewGuid().ToString('N'))
$outputDir = Join-Path $repo 'dist\android'
$keyDir = Join-Path $repo '.task\android'
New-Item -ItemType Directory -Force -Path "$build\classes", "$build\tests", "$build\dex", "$build\res\drawable", $outputDir, $keyDir | Out-Null
$oldJavaHome = $env:JAVA_HOME
try {
    $env:JAVA_HOME = $jdk
    Copy-Item -Path "$repo\android\res\*" -Destination "$build\res" -Recurse
    Copy-Item -LiteralPath (Join-Path $repo 'backend\assets\icon.png') -Destination "$build\res\drawable\icon.png"
    Invoke-Native "$tools\aapt2.exe" @('compile', '--dir', "$build\res", '-o', "$build\resources.zip")
    Invoke-Native "$tools\aapt2.exe" @('link', '-o', "$build\unsigned.apk", '-I', $androidJar, '--manifest', "$repo\android\AndroidManifest.xml", '--min-sdk-version', '26', '--target-sdk-version', '35', '--version-code', '6', '--version-name', '1.5', "$build\resources.zip")
    $sources = @(Get-ChildItem "$repo\android\src" -Filter *.java -Recurse | Select-Object -ExpandProperty FullName)
    Invoke-Native "$jdk\bin\javac.exe" (@('-encoding', 'UTF-8', '--release', '8', '-classpath', $androidJar, '-d', "$build\classes") + $sources)
    Invoke-Native "$jdk\bin\javac.exe" @('-encoding', 'UTF-8', '--release', '8', '-classpath', "$build\classes", '-d', "$build\tests", "$repo\android\tests\LanAddressTest.java")
    Invoke-Native "$jdk\bin\java.exe" @('-ea', '-cp', "$build\classes;$build\tests", 'LanAddressTest')
    $classes = @(Get-ChildItem "$build\classes" -Filter *.class -Recurse | Select-Object -ExpandProperty FullName)
    Invoke-Native "$tools\d8.bat" (@('--min-api', '26', '--lib', $androidJar, '--output', "$build\dex") + $classes)
    Push-Location "$build\dex"
    try { Invoke-Native "$tools\aapt.exe" @('add', '-f', "$build\unsigned.apk", 'classes.dex') } finally { Pop-Location }
    Invoke-Native "$tools\zipalign.exe" @('-f', '4', "$build\unsigned.apk", "$build\aligned.apk")
    # ローカル導入用 debug 署名。鍵は生成物ディレクトリへ保持し、リポジトリへ含めない。
    $key = Join-Path $keyDir 'debug.keystore'
    if (-not (Test-Path -LiteralPath $key)) {
        Invoke-Native "$jdk\bin\keytool.exe" @('-genkeypair', '-keystore', $key, '-storepass', 'android', '-keypass', 'android', '-alias', 'androiddebugkey', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000', '-dname', 'CN=Android Debug,O=Android,C=US')
    }
    $apk = Join-Path $outputDir 'SplatReplay.apk'
    Invoke-Native "$tools\apksigner.bat" @('sign', '--ks', $key, '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', $apk, "$build\aligned.apk")
    Invoke-Native "$tools\apksigner.bat" @('verify', '--verbose', $apk)
    Get-FileHash -LiteralPath $apk -Algorithm SHA256
}
finally {
    $env:JAVA_HOME = $oldJavaHome
    $resolvedBuild = [IO.Path]::GetFullPath($build)
    $tempRoot = [IO.Path]::GetFullPath((Join-Path $repo '.tmp')) + '\'
    if (-not $resolvedBuild.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid build cleanup path.' }
    Remove-Item -LiteralPath $resolvedBuild -Recurse -Force
}
