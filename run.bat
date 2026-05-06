@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 首次运行创建 .env
if not exist .env (
    copy .env.example .env
    echo [ChaseBase] 已生成 .env，请填写 ANTHROPIC_API_KEY 后重启。
    notepad .env
    exit /b
)

REM 创建虚拟环境
if not exist .venv (
    echo [ChaseBase] 正在创建虚拟环境...
    python -m venv .venv
)

call .venv\Scripts\activate

REM 安装依赖
echo [ChaseBase] 检查依赖...
pip install -r requirements.txt -q

REM 打开浏览器（等 2 秒让服务启动）
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000

REM 启动服务
echo [ChaseBase] 启动服务 http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
