@echo off
chcp 65001 >nul
set "PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\standalone-env\Scripts\python.exe"
"%PY%" "D:\Comfyui\split_dance.py" %*
pause
