@echo off
rem Lanzador del repo de grafo_ia para Windows: graph.cmd install ^| uninstall ^| ^<comando^>
setlocal
set "REPO=%~dp0"
if /i "%~1"=="install" goto :instalar
if /i "%~1"=="uninstall" goto :instalar
if not exist "%REPO%.venv\Scripts\graph.exe" (
  echo grafo_ia no esta instalado: corre graph.cmd install 1>&2
  exit /b 2
)
"%REPO%.venv\Scripts\graph.exe" %*
exit /b %ERRORLEVEL%
:instalar
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%REPO%scripts\install.py" %*
) else (
  python "%REPO%scripts\install.py" %*
)
exit /b %ERRORLEVEL%
