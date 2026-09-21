: << 'CMDBLOCK'
@echo off
REM Cross-platform polyglot wrapper for the drogon plugin hooks.
REM On Windows: msys bash invokes .cmd files through cmd.exe, which runs the
REM batch portion below - it locates Git for Windows bash and runs the target
REM extensionless hook script through it.
REM On Unix: bash reads this same file as a shell script (: is a no-op), the
REM heredoc swallows the batch section, and the bash dispatch at the bottom runs.
REM
REM Hook scripts use extensionless filenames (session-start / post-tool-use)
REM so the host's Windows auto-detection - which prepends "bash" to any
REM command containing ".sh" - does not interfere.
REM
REM Usage: run-hook.cmd <session-start|post-tool-use> [args...]

if "%~1"=="" (
    echo run-hook.cmd: missing hook name >&2
    exit /b 1
)

set "HOOK_DIR=%~dp0"

REM Try Git for Windows bash in standard locations first
if exist "C:\Program Files\Git\bin\bash.exe" (
    "C:\Program Files\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)
if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    "C:\Program Files (x86)\Git\bin\bash.exe" "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM Try bash on PATH (user-installed Git Bash, MSYS2, Cygwin, WSL git)
where bash >nul 2>nul
if %ERRORLEVEL% equ 0 (
    bash "%HOOK_DIR%%~1" %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %ERRORLEVEL%
)

REM No bash found - exit silently rather than error.
REM (Plugin still works, just without SessionStart context injection.)
exit /b 0
CMDBLOCK

# ---- bash section (Unix path; Windows reaches the target script via the
# ---- batch section above, so this dispatch is Unix-only) --------------------
set -eu

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"

case "${1:-}" in
    session-start)
        exec bash "$HOOK_DIR/session-start"
        ;;
    post-tool-use)
        exec bash "$HOOK_DIR/post-tool-use"
        ;;
    "")
        echo "run-hook.cmd: missing hook name" >&2
        exit 1
        ;;
    *)
        echo "run-hook.cmd: unknown hook: $1" >&2
        exit 1
        ;;
esac
