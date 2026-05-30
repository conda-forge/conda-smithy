setlocal enableextensions enabledelayedexpansion

set PAGEFILE_SIZE=%1

:: Increase pagefile size, cf. https://github.com/conda-forge/conda-forge-ci-setup-feedstock/issues/155
set ThisScriptsDirectory=%~dp0
set EntryPointPath=%ThisScriptsDirectory%SetPageFileSize.ps1
:: Try to use different drive than CONDA_BLD_PATH-location for pagefile, if available
set PageFileDrive=C:
if /i "%CONDA_BLD_PATH:~0,2%" == "C:" (
    if exist D:\ set "PageFileDrive=D:"
)

:: Only run if PAGEFILE_SIZE is set; EntryPointPath needs to be set outside if-condition when not using EnableDelayedExpansion.
if "%PAGEFILE_SIZE%" GTR "0" (
    if not "%PageFileDrive%" == "" (
        echo CONDA_BLD_PATH=%CONDA_BLD_PATH%; Setting pagefile size to %PAGEFILE_SIZE% GiB in %PageFileDrive%
        REM Inspired by:
        REM https://blog.danskingdom.com/allow-others-to-run-your-powershell-scripts-from-a-batch-file-they-will-love-you-for-it/
        REM Drive-letter needs to be escaped in quotes
        PowerShell -NoProfile -ExecutionPolicy Bypass -Command "& '%EntryPointPath%' -MinimumSize "%PAGEFILE_SIZE%GB" -MaximumSize "%PAGEFILE_SIZE%GB" -DiskRoot \"%PageFileDrive%\""
    )
)
exit /b
