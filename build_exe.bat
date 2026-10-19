@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto directory_error
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 scripts\build_exe.py
goto finished
:use_python
python scripts\build_exe.py
:finished
set "build_result=%errorlevel%"
popd
goto exit_build
:directory_error
echo Cannot open the project directory.
set "build_result=1"
:exit_build
if not "%build_result%"=="0" echo Build failed. See the error above.
if /I not "%~1"=="--no-pause" pause
exit /b %build_result%
