@echo off
rem Syncs EU5 script/data files into this folder after a patch.
rem Mirrors: deletes files here that a patch removed from the game.
rem Excludes: gfx, fonts, music, sound, content_source, non-English localization.

set "SRC=C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V"
set "DST=%~dp0"
set "XLANG=braz_por french german japanese korean polish russian simp_chinese spanish turkish"

echo === game ===
robocopy "%SRC%\game" "%DST%game" /MIR /XD gfx fonts music sound content_source %XLANG% /NFL /NDL /NP /NJH

echo === jomini ===
robocopy "%SRC%\jomini" "%DST%jomini" /MIR /XD gfx fonts music sound %XLANG% /NFL /NDL /NP /NJH

echo === clausewitz ===
robocopy "%SRC%\clausewitz" "%DST%clausewitz" /MIR /XD gfx fonts music sound %XLANG% /NFL /NDL /NP /NJH

echo === binaries ===
if not exist "%DST%binaries" mkdir "%DST%binaries"
for %%F in (eu5.exe PDXSDK.dll pdx_red_king.dll checksum.txt eu5.exe.manifest) do (
    copy /Y "%SRC%\binaries\%%F" "%DST%binaries\" >nul && echo   %%F
)

echo.
echo Done. Game version checksum:
type "%DST%binaries\checksum.txt" 2>nul
pause
