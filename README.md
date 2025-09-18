# PMSManageBot

基于 FastAPI + Telegram Bot 的媒体管理助手，支持 WebApp 前端（Vue 3 + Vuetify）与多项自动化任务（APScheduler）。

## 功能概览
- Telegram 机器人（python-telegram-bot）
- FastAPI 提供 Web API 与静态前端托管
- 定时任务（APScheduler）
- Redis 缓存
- SQLite 数据库存储（首次启动自动建表）
- 前端：Vue 3 + Vuetify 3（使用 Vue CLI 构建）

## 目录结构
- `src/app/` 后端源码（包名：`app`）
- `webapp-frontend/` 前端源码（Vue CLI）
- `data/` 运行时数据（.env、data.db 等）

## 环境准备
- Python 3.11+
- Node.js 18（构建前端）
- Redis（可选，默认连接 `localhost:6379`）

## 快速开始（本地）
1. 克隆并进入项目目录后，复制环境变量示例：
   ```bash
   cp .env.example data/.env
   # 至少设置 TG_API_TOKEN、ADMIN_CHAT_ID
   ```
2. 安装后端依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 构建前端（可选，若启用 WebApp 且需要本地访问静态资源）：
   ```bash
   cd webapp-frontend
   npm ci || npm install
   npm run build
   ```
4. 启动（默认启用 WebApp）：
   ```bash
   export PYTHONPATH=src
   python -m app.main
   # 仅 API 调试：
   # uvicorn app.webapp:app --app-dir src --host 0.0.0.0 --port 5000
   ```

首启时将自动创建 `data/data.db` 并建表。

## Docker 运行
- 构建并运行（包含前端构建阶段）：
  ```bash
  docker compose up --build -d
  ```
- 映射端口：`5000:5000`
- 数据目录挂载：`./data:/app/data`

## 部署建议
- 生产环境请将 `WEBAPP_ENABLE=true`，并根据需要将前端 `.env.production` 中的 `VUE_APP_API_URL` 指向你的后端域名；或使用同域部署，前端通过相对路径访问 API。
- 建议使用 Docker 多阶段构建，减少环境差异带来的问题。
- 生产环境请收紧 CORS 配置（`src/app/webapp/__init__.py` 中的 `allow_origins`）。

## 关键配置
- 配置来源：`data/.env`（详见 `data/.env.example` 与根目录 `.env.example`）
- WebApp 静态目录：自动定位至 `<项目根>/webapp-frontend/dist`，可通过 `WEBAPP_STATIC_DIR` 覆盖。
- WebApp 开关：`WEBAPP_ENABLE=true|false`
- 会话密钥：`WEBAPP_SESSION_SECRET_KEY`

## 常见问题
- 无法导入 `app.config`：确保已生成 `src/app/config.py`（本仓库已包含）且 `PYTHONPATH=src`。
- 首次运行数据库查询报错：首次启动会自动建表，如仍异常可删除 `data/data.db` 后重启。
- 静态资源 404：确认已构建前端并确保 `WEBAPP_STATIC_DIR` 指向正确的 `dist/` 目录。

## 许可证
本项目仅供学习与演示。
