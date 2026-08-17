@echo off
chcp 65001 >nul
title 打包 冒险岛怀旧服辅助

REM ========== 打包模式选择 ==========
:MENU
echo.
echo ======================================
echo   冒险岛怀旧服辅助 - 打包工具
echo ======================================
echo.
echo   1. 带控制台窗口（便于调试看日志）
echo   2. 无控制台窗口（干净，双击即运行）
echo   3. 退出
echo.
set /p choice="请选择 [1-3]: "
if "%choice%"=="1" set "WINDOW_FLAG=--console" & goto BUILD
if "%choice%"=="2" set "WINDOW_FLAG=--windowed" & goto BUILD
if "%choice%"=="3" exit /b
goto MENU

:BUILD
echo.
echo ========== 开始打包 ==========
echo   模式: %WINDOW_FLAG%
echo.

REM 清理旧产物
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "冒险岛怀旧服辅助.spec" del /q "冒险岛怀旧服辅助.spec"

REM ---------- 打包 GUI 版 ----------
pyinstaller %WINDOW_FLAG% ^
    --noconfirm ^
    --clean ^
    --name "冒险岛怀旧服辅助" ^
    --collect-all opencv-python ^
    --collect-all pymem ^
    --copy-metadata mss ^
    --copy-metadata pydirectinput ^
    --copy-metadata keyboard ^
    --copy-metadata Pillow ^
    --copy-metadata numpy ^
    --add-data "templates;templates" ^
    --add-data "README.md;." ^
    gui.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查上方日志
    goto END
)

REM ---------- 复制额外运行时文件 ----------
set "OUT=dist\冒险岛怀旧服辅助"
if exist "%OUT%" (
    REM 复制启动用的说明（避免用户找不到主程序）
    echo 双击运行「冒险岛怀旧服辅助.exe」（读内存需要以管理员身份运行） > "%OUT%\__使用说明__.txt"
    REM 复制 templates/README.txt
    if exist "templates\README.txt" copy /y "templates\README.txt" "%OUT%\templates\README.txt" >nul
    REM 复制 requirements 供参考
    copy /y "requirements.txt" "%OUT%\" >nul
    echo.
    echo ========== 打包完成 ==========
    echo   产物目录: %cd%\%OUT%
    echo   主程序: %OUT%\冒险岛怀旧服辅助.exe
    echo.
    echo 注意:
    echo   - settings.json（用户配置）会在首次运行后生成在主程序同目录
    echo   - 怪物模板图片请放到 %OUT%\templates\ 目录
    echo   - 读取内存模式需要：管理员身份运行 ^+ 进程名正确 ^+ 偏移正确
) else (
    echo.
    echo [警告] 未找到产物目录 dist\冒险岛怀旧服辅助
)

:END
echo.
pause
