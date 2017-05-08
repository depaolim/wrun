@echo off
cd
if "%1"=="ERROR" (
    echo err_msg %1 1>&2
    exit /b 1
)
echo hello %1
