@echo off
setlocal
cd /d "%~dp0"

C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe ^
/platform:x86 ^
/reference:"OSIsoft.PISDK.dll" ^
/reference:"OSIsoft.PISDKCommon.dll" ^
/reference:"OSIsoft.PITimeServer.dll" ^
/reference:System.Web.Extensions.dll ^
/out:PIReader.exe ^
TimeExpressionParser.cs ^
Program.cs

if errorlevel 1 (
    echo [ERROR] PIReader compile failed.
) else (
    echo [OK] PIReader.exe compiled successfully.
)

pause