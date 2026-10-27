@echo off
chcp 65001 >nul
echo ========================================================
echo   🐇 兔子洞筆記 - 一鍵建置並發布網站至 GitHub
echo ========================================================
echo.
echo [1/3] 正在掃描文獻與音檔，重新建置網頁與 RSS...
python "%~dp0build_podcast.py"
if %errorlevel% neq 0 (
    echo [ERROR] 建置失敗！
    pause
    exit /b %errorlevel%
)

echo.
echo [2/3] 正在將更新推送到 GitHub...
cd /d "%~dp0"
git add -A
git commit -m "Update podcast content and reference docs"
git push
if %errorlevel% neq 0 (
    echo [ERROR] 推送失敗，請檢查網路連線或登入狀態！
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo [OK] 發布成功！GitHub Pages 將在 30 秒內自動更新生效：
echo      https://tzejen.github.io/rabbit-hole/
echo ========================================================
echo.
pause
