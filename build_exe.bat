@echo off
rem Copyright (c) 2026 粗糙的鹿包 (Clumsy Fawn) · X: https://x.com/svip1321
rem 仅限个人非商业使用，禁止商用（详见 LICENSE.txt） / Non-commercial use only. Commercial use is prohibited.
rem
rem 把软件打包成 exe：鹿包的GPU格式转换 (Clumsy Fawn GPU Converter)
rem 为了尽量不被杀毒软件误报，这个脚本做了这些事：
rem   1. 在单独的干净环境（.build_env）里打包，只带软件真正用到的东西，体积小、可疑的东西少
rem   2. 文件夹模式（--onedir），不用「单个 exe 自解压」模式（那种最容易被当成病毒）
rem   3. 不用 UPX 压缩（--noupx），也不加密、不混淆、不要求管理员权限
rem   4. 写入完整的版本信息：作者、版权、版本号、产品名（右键 exe → 属性 → 详细信息 能看到）
rem   5. 打包完生成 SHA256 校验值，方便被误报时提交给杀毒厂商
chcp 65001 >nul
cd /d "%~dp0"
set APP=ClumsyFawnGPUConverter
set OUT=dist\%APP%
echo ============================================
echo   鹿包的GPU格式转换 (Clumsy Fawn GPU Converter)
echo   打包成 exe   作者：粗糙的鹿包   版本 1.0.0
echo ============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo 找不到 Python 启动器 py，请先安装 Python 3.8 或更高版本（安装时勾选 Add Python to PATH）
  goto fail
)

echo [1/5] 准备干净的打包环境 .build_env（第一次会慢一点）...
if not exist ".build_env\Scripts\python.exe" (
  py -m venv .build_env
  if errorlevel 1 goto fail
)
set PY=.build_env\Scripts\python.exe
rem 看看这次用的 Python 是 64 位还是 32 位：打包出来的 exe 和它一样
set BITS=64
for /f %%b in ('%PY% -c "import sys; print(sys.maxsize.bit_length() + 1)"') do set BITS=%%b
if "%BITS%"=="64" (
  echo    这次打包的是 64 位版本（x64）：64 位 Windows 10 / 11 和 ARM 版 Windows 11 都能用
) else (
  echo    注意：这次用的是 %BITS% 位 Python，打包出来的是 32 位版本（x86）
  echo    而 ffmpeg 是 64 位的，32 位系统上还是转换不了，建议安装 64 位 Python 再打包
)
"%PY%" -m pip install -q -U pip
rem pillow 只在打包时用来把 ico.png 转成 exe 图标，不会打包进软件里
"%PY%" -m pip install -q -U pyinstaller send2trash tkinterdnd2 pillow
if errorlevel 1 goto fail

echo.
echo [2/5] 清理上次打包留下的文件...
if exist "build" rmdir /s /q "build"
if exist "%OUT%" rmdir /s /q "%OUT%"
if exist "%APP%.spec" del /q "%APP%.spec"

rem 软件图标：lubao_converter\assets\ico.png（建议 512x512），没有就用默认图标
set ICON=
if exist "lubao_converter\assets\ico.png" (
  set ICON=--icon "lubao_converter\assets\ico.png"
) else (
  echo    注意：没找到 lubao_converter\assets\ico.png，这次打包的 exe 会用默认图标
)

echo.
echo [3/5] 开始打包（文件夹模式、不压缩、带版本信息）...
"%PY%" -m PyInstaller --noconfirm --clean --onedir --noupx --windowed ^
  --name "%APP%" ^
  %ICON% ^
  --version-file "version_info.txt" ^
  --add-data "lubao_converter\assets;lubao_converter\assets" ^
  --add-data "lubao_converter\lang;lubao_converter\lang" ^
  --hidden-import lubao_converter.qr_data ^
  --collect-all tkinterdnd2 ^
  --exclude-module PIL --exclude-module numpy --exclude-module unittest --exclude-module pydoc ^
  main.pyw
if errorlevel 1 goto fail

echo.
echo [4/5] 复制 ffmpeg 和许可协议...
if exist "FFMPEG\bin\ffmpeg.exe" copy /y "FFMPEG\bin\ffmpeg.exe" "%OUT%\" >nul
if exist "FFMPEG\bin\ffprobe.exe" copy /y "FFMPEG\bin\ffprobe.exe" "%OUT%\" >nul
if exist "ffmpeg.exe" copy /y "ffmpeg.exe" "%OUT%\" >nul
if exist "ffprobe.exe" copy /y "ffprobe.exe" "%OUT%\" >nul
if exist "FFMPEG\LICENSE" copy /y "FFMPEG\LICENSE" "%OUT%\FFMPEG_LICENSE.txt" >nul
copy /y "LICENSE.txt" "%OUT%\" >nul
copy /y "README.md" "%OUT%\" >nul
if not exist "%OUT%\ffmpeg.exe" echo    注意：没找到 ffmpeg.exe，打包出来的软件需要用户自己装 ffmpeg

echo.
echo [5/5] 生成 SHA256 校验值（被误报时提交给杀毒厂商用）...
certutil -hashfile "%OUT%\%APP%.exe" SHA256 > "%OUT%\SHA256.txt"

echo.
echo ============================================
echo   打包完成！
echo   程序：%OUT%\%APP%.exe   （%BITS% 位版本）
echo   发给别人时，把整个 %OUT% 文件夹压缩成 zip 发过去就行
echo.
echo   如果被杀毒软件误报，可以把 exe 提交给厂商申诉（一般 1~3 天解除）：
echo     微软 Defender：https://www.microsoft.com/en-us/wdsi/filesubmission
echo     火绒：https://www.huorong.cn  （官网「误报反馈」）
echo     360：https://ts.isafe.360.cn
echo     腾讯电脑管家：https://guanjia.qq.com  （官网「误报申诉」）
echo ============================================
pause
exit /b 0

:fail
echo.
echo 打包失败了，把上面的报错截图发给鹿包看看吧
pause
exit /b 1
