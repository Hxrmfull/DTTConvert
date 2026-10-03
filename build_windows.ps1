# Собирает Windows-сборки DTTConvert и упаковывает их в архивы для релиза.
#
# Вариантов два:
#   with-ffmpeg    — ffmpeg.exe и ffprobe.exe лежат внутри, ставить ничего
#                    не нужно, но архив тяжёлый.
#   without-ffmpeg — только программа. Видео и GIF заработают, когда рядом
#                    с DTTConvert.exe появится ffmpeg.exe (или FFmpeg будет
#                    в PATH). Картинки работают и без него.
#
# Режим --onedir: рядом с exe лежит папка _internal с библиотеками.
# Раньше был --onefile — один файл, который при каждом запуске распаковывал
# себя во временную папку. Это давало задержку старта и регулярно вызывало
# ложные срабатывания антивирусов: «программа сама себя распаковала и
# выполнила код из TEMP» — известная беда PyInstaller.
#
# Примеры:
#   .\build_windows.ps1                              # обе сборки и оба архива
#   .\build_windows.ps1 -Variant without-ffmpeg      # только лёгкая
#   .\build_windows.ps1 -FfmpegDir "D:\ffmpeg\bin"   # своя копия FFmpeg
#   .\build_windows.ps1 -NoZip                       # без упаковки в zip
#   .\build_windows.ps1 -Installer                   # плюс установщик (Inno Setup 6)

param(
    [ValidateSet("both", "with-ffmpeg", "without-ffmpeg")]
    [string]$Variant = "both",
    [string]$Python = "py",
    [string]$FfmpegDir,
    [switch]$NoZip,
    [switch]$Installer
)

$ErrorActionPreference = "Stop"

# Название и версия берутся из app_info.py: иначе имена архивов разъезжаются
# с тем, что программа показывает в заголовке окна.
$appInfo = Get-Content -LiteralPath (Join-Path $PSScriptRoot "app_info.py") -Raw -Encoding UTF8
if ($appInfo -notmatch 'APP_NAME\s*=\s*"([^"]+)"') { throw "В app_info.py не найдено APP_NAME." }
$appName = $Matches[1]
if ($appInfo -notmatch 'APP_VERSION\s*=\s*"([^"]+)"') { throw "В app_info.py не найдено APP_VERSION." }
$appVersion = $Matches[1]

Write-Host "Сборка $appName $appVersion" -ForegroundColor Cyan

$needsFfmpeg = $Variant -ne "without-ffmpeg"
$ffmpeg = $null
$ffprobe = $null
$ffmpegRoot = $null

if ($needsFfmpeg) {
    if (-not $FfmpegDir) {
        $ffmpegCommand = Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue
        if (-not $ffmpegCommand) { $ffmpegCommand = Get-Command "ffmpeg" -ErrorAction SilentlyContinue }
        if ($ffmpegCommand) { $FfmpegDir = Split-Path -Parent $ffmpegCommand.Source }
        else { $FfmpegDir = "C:\ffmpeg\bin" }
    }
    $ffmpeg = Join-Path $FfmpegDir "ffmpeg.exe"
    $ffprobe = Join-Path $FfmpegDir "ffprobe.exe"
    if (!(Test-Path -LiteralPath $ffmpeg) -or !(Test-Path -LiteralPath $ffprobe)) {
        throw "Не найдены ffmpeg.exe и ffprobe.exe в $FfmpegDir. Установите FFmpeg (чтобы он определялся через PATH), укажите путь явно через -FfmpegDir или соберите только лёгкий вариант: -Variant without-ffmpeg"
    }
    $ffmpegRoot = Split-Path -Parent $FfmpegDir
    Write-Host "FFmpeg из: $FfmpegDir"

    # Контрольные суммы вшиваемых бинарников. При первой сборке они
    # записываются в файл, при последующих — сверяются, чтобы подмена
    # ffmpeg.exe не прошла незамеченной.
    $checksumFile = Join-Path $PSScriptRoot "ffmpeg_checksums.txt"
    $currentSums = [ordered]@{}
    foreach ($binary in @($ffmpeg, $ffprobe)) {
        $name = Split-Path -Leaf $binary
        $currentSums[$name] = (Get-FileHash -Algorithm SHA256 -LiteralPath $binary).Hash
        Write-Host "  $name SHA256: $($currentSums[$name])"
    }
    if (Test-Path -LiteralPath $checksumFile) {
        $known = @{}
        foreach ($line in Get-Content -LiteralPath $checksumFile) {
            if ($line -match '^\s*([^\s#]+)\s+([0-9A-Fa-f]{64})\s*$') { $known[$Matches[1]] = $Matches[2].ToUpper() }
        }
        foreach ($name in $currentSums.Keys) {
            if ($known.ContainsKey($name) -and $known[$name] -ne $currentSums[$name]) {
                throw "Контрольная сумма $name не совпадает с записанной в $checksumFile. Если FFmpeg обновлялся намеренно — удалите этот файл и соберите заново."
            }
        }
        Write-Host "Контрольные суммы совпадают с записанными."
    } else {
        $lines = foreach ($name in $currentSums.Keys) { "$name $($currentSums[$name])" }
        Set-Content -LiteralPath $checksumFile -Value $lines -Encoding utf8
        Write-Host "Контрольные суммы записаны в $checksumFile"
    }
}

$iconArgs = @()
$icon = Join-Path $PSScriptRoot "icon.ico"
if (Test-Path -LiteralPath $icon) {
    # --icon задаёт значок самого exe, --add-data кладёт файл внутрь сборки,
    # чтобы приложение могло поставить иконку окну во время работы.
    $iconArgs = @("--icon", $icon, "--add-data", "$icon;.")
} else {
    Write-Host "Иконка icon.ico не найдена — собираю со значком по умолчанию." -ForegroundColor Yellow
}

$releaseDir = Join-Path $PSScriptRoot "release"
if (-not $NoZip -and !(Test-Path -LiteralPath $releaseDir)) {
    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
}

$built = @()

function Build-Variant([string]$Name, [bool]$Bundle) {
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan

    $distPath = Join-Path $PSScriptRoot "dist\$Name"
    $workPath = Join-Path $PSScriptRoot "build\$Name"

    $binaryArgs = @()
    if ($Bundle) {
        $binaryArgs = @("--add-binary", "$ffmpeg;.", "--add-binary", "$ffprobe;.")
    }

    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name $appName `
        --distpath $distPath `
        --workpath $workPath `
        --specpath $workPath `
        @binaryArgs `
        @iconArgs `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "Сборка «$Name» завершилась с ошибкой." }

    $appDir = Join-Path $distPath $appName

    if ($Bundle) {
        # Лицензия FFmpeg едет вместе с бинарником: он распространяется
        # по GPL/LGPL, и её текст обязан лежать рядом.
        foreach ($item in @("LICENSE", "README.txt")) {
            $source = Join-Path $ffmpegRoot $item
            if (Test-Path -LiteralPath $source) {
                Copy-Item -LiteralPath $source -Destination (Join-Path $appDir "FFmpeg-$item") -Force
            }
        }
    } else {
        # В лёгкой сборке объясняем прямо в папке, где взять FFmpeg:
        # страницу проекта рядом с распакованным архивом не открыть.
        $note = @"
DTTConvert $appVersion — сборка без FFmpeg

Конвертация изображений (JPG, PNG, WEBP, BMP, AVIF) работает сразу.
Для видео, GIF, стикеров и звука нужен FFmpeg — любым из двух способов:

1. Положите ffmpeg.exe и ffprobe.exe рядом с $appName.exe, в эту же папку.
2. Или установите FFmpeg и добавьте его в переменную PATH.

Скачать сборку для Windows: https://www.gyan.dev/ffmpeg/builds/
(подойдёт release-essentials или release-full)

Копия рядом с программой имеет приоритет над установленной в системе,
поэтому обновить FFmpeg можно простой заменой файла.
"@
        Set-Content -LiteralPath (Join-Path $appDir "FFmpeg - как добавить.txt") -Value $note -Encoding utf8
    }

    $size = [math]::Round(((Get-ChildItem -LiteralPath $appDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
    Write-Host "Готово: $appDir ($size МБ)" -ForegroundColor Green

    if (-not $NoZip) {
        $zipName = "$appName-$appVersion-windows-x64-$Name.zip"
        $zipPath = Join-Path $releaseDir $zipName
        if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
        Compress-Archive -Path $appDir -DestinationPath $zipPath -CompressionLevel Optimal
        $zipSize = [math]::Round(((Get-Item -LiteralPath $zipPath).Length / 1MB), 1)
        Write-Host "Архив:  $zipPath ($zipSize МБ)" -ForegroundColor Green
        $script:built += [pscustomobject]@{ Вариант = $Name; Архив = $zipName; "МБ" = $zipSize }
    } else {
        $script:built += [pscustomobject]@{ Вариант = $Name; Архив = "(не упаковано)"; "МБ" = $size }
    }
}

if ($Variant -eq "both" -or $Variant -eq "with-ffmpeg") { Build-Variant "with-ffmpeg" $true }
if ($Variant -eq "both" -or $Variant -eq "without-ffmpeg") { Build-Variant "without-ffmpeg" $false }

if ($Installer) {
    # Установщик собирается из готовой папки: ярлык в «Пуске», удаление
    # через «Приложения», обновление поверх старой версии. На каждый
    # собранный вариант — свой установщик: с FFmpeg для всех и лёгкий для
    # тех, у кого FFmpeg уже стоит.
    $setupVariants = switch ($Variant) {
        "with-ffmpeg" { @("with-ffmpeg") }
        "without-ffmpeg" { @("without-ffmpeg") }
        default { @("with-ffmpeg", "without-ffmpeg") }
    }
    $candidates = @(
        (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $iscc = $candidates | Select-Object -First 1
    if (-not $iscc) {
        throw "Не найден Inno Setup 6 (ISCC.exe). Установите его: winget install JRSoftware.InnoSetup — или скачайте с https://jrsoftware.org/isdl.php"
    }
    if (!(Test-Path -LiteralPath $releaseDir)) {
        New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    }
    foreach ($setupVariant in $setupVariants) {
        Write-Host ""
        Write-Host "=== Установщик ($setupVariant) ===" -ForegroundColor Cyan
        Push-Location $PSScriptRoot
        try {
            & $iscc "/DAppVersion=$appVersion" "/DVariant=$setupVariant" "installer.iss"
            if ($LASTEXITCODE -ne 0) { throw "Сборка установщика «$setupVariant» завершилась с ошибкой." }
        } finally {
            Pop-Location
        }
        # Имя — как у архивов: вариант виден прямо в имени файла.
        $setupName = "$appName-$appVersion-windows-x64-$setupVariant-setup.exe"
        $setupPath = Join-Path $releaseDir $setupName
        $setupSize = [math]::Round(((Get-Item -LiteralPath $setupPath).Length / 1MB), 1)
        Write-Host "Установщик: $setupPath ($setupSize МБ)" -ForegroundColor Green
        $script:built += [pscustomobject]@{ Вариант = "setup ($setupVariant)"; Архив = $setupName; "МБ" = $setupSize }
    }
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
$built | Format-Table -AutoSize
Write-Host "Переносить нужно всю папку целиком — рядом с exe лежит _internal."
if (-not $NoZip) { Write-Host "Архивы готовы к загрузке в релиз на GitHub." }
