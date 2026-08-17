@echo off
chcp 65001 >nul
title 冒险岛怀旧服辅助

REM 检查是否已有管理员权限（读游戏内存需要）
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM 用官方 Python 3.13 启动 GUI（已加入系统 PATH）
"C:\Users\WA05922\AppData\Local\Programs\Python\Python313\python.exe" "%~dp0gui.py"

if %errorlevel% neq 0 (
    echo.
    echo 启动失败，错误码 %errorlevel%
)
pause
