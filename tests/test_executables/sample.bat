@echo off
setlocal DisableDelayedExpansion

cd
if "%1"=="ERROR" (
    echo err_msg %1 1>&2
    exit /b 1
)
if "%1"=="STDIN" (
    for /F "tokens=*" %%a in ('findstr /n $') do (
      set "line=%%a"
      setlocal EnableDelayedExpansion
      set "line=!line:*:=!"
      echo(!line!
      endlocal
    )
    exit /b 0
)
echo hello %1
