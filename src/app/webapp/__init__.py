import secrets
import os
import re
from pathlib import Path

from app.config import settings
from app.log import logger
from app.webapp.middlewares import TelegramAuthMiddleware
from app.webapp.routers import rankings_router, system_router, user_router
from app.webapp.routers.activities.auction import router as auction_router
from app.webapp.routers.activities.luckywheel import router as luckywheel_router
from app.webapp.routers.admin import router as admin_router
from app.webapp.routers.invitation import router as invitation_router
from app.webapp.routers.premium import router as premium_router
from app.webapp.startup.lifespan import lifespan
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware

# 创建 FastAPI 应用
app = FastAPI(
    title="PMSManageBot API",
    description="API for PMSManageBot WebApp",
    lifespan=lifespan,
)

# 配置 SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    # 会话密钥读取顺序：环境变量(WEBAPP_SESSION_SECRET_KEY/SESSION_SECRET_KEY) → settings 同名字段 → 随机
    secret_key=(
        os.getenv("WEBAPP_SESSION_SECRET_KEY")
        or os.getenv("SESSION_SECRET_KEY")
        or getattr(settings, "WEBAPP_SESSION_SECRET_KEY", None)
        or getattr(settings, "SESSION_SECRET_KEY", None)
        or secrets.token_urlsafe(32)
    ),
    session_cookie="pmsmanagebot_session",
    max_age=86400,  # 1天过期
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中，应该设置为特定的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加 Telegram 认证中间件
app.add_middleware(TelegramAuthMiddleware)

# 注册路由
app.include_router(user_router)
app.include_router(rankings_router)
app.include_router(system_router)  # 添加系统统计路由
app.include_router(invitation_router)  # 添加邀请码路由
app.include_router(premium_router)  # 添加 Premium 路由
app.include_router(admin_router)  # 添加管理员路由
app.include_router(luckywheel_router, prefix="/api")  # 添加幸运大转盘路由
app.include_router(auction_router, prefix="/api")  # 添加竞拍活动路由


def setup_static_files():
    """配置静态文件服务"""
    static_dir = Path(settings.WEBAPP_STATIC_DIR).absolute()
    if not static_dir.exists():
        logger.warning(f"WebApp 静态文件目录不存在: {static_dir}")
        return False

    try:
        # 在挂载之前，尝试将 WEBAPP_TITLE 写入磁盘上的 index.html，保证 /app/ 静态返回也生效
        try:
            title_override = _get_title_override()
            if title_override:
                _apply_title_to_index_file(static_dir, title_override)
        except Exception as e:
            logger.debug(f"预写入 WEBAPP_TITLE 到 index.html 失败: {e}")

        # 注意：避免挂载在根路径 "/"，否则会遮蔽 /api/* 路由
        app.mount("/app", StaticFiles(directory=str(static_dir), html=True), name="webapp")
        return True
    except Exception as e:
        logger.error(f"挂载 WebApp 静态文件失败: {e}")
        return False


def _get_title_override() -> str | None:
    """获取需要注入的 WEBAPP_TITLE：优先环境变量，然后 settings，最后 .env 文件兜底。"""
    # 1) 环境变量优先（便于 systemd 覆盖）
    title = os.getenv("WEBAPP_TITLE") or os.getenv("SITE_NAME")
    if title:
        return title.strip().strip('"').strip("'")

    # 2) settings（如果配置里提供了同名字段）
    title = getattr(settings, "WEBAPP_TITLE", None) or getattr(settings, "SITE_NAME", None)
    if isinstance(title, str) and title.strip():
        return title.strip().strip('"').strip("'")

    # 3) 兜底：直接从 .env 文件读取（如果存在且包含该项）
    try:
        env_path = getattr(settings, "ENV_FILE_PATH", None)
        if env_path:
            env_path = Path(env_path)
            if env_path.exists():
                with env_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        key = line.split("=", 1)[0].strip()
                        if key in ("WEBAPP_TITLE", "SITE_NAME"):
                            value = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if value:
                                return value
    except Exception as e:
        logger.debug(f"读取 .env 中 WEBAPP_TITLE 失败: {e}")
    return None


def _apply_title_to_index_file(static_dir: Path, title: str):
    """直接修改磁盘上的 index.html，将 <title> 注入为指定值。

    - 若存在 <title> 则替换首个
    - 否则在 </head> 前插入；若无 head，则补一个最小 head
    - 会在同目录创建一次性备份 index.html.bak（如不存在）
    """
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return
    html = index_file.read_text(encoding="utf-8", errors="ignore")
    before = html
    pattern = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
    if pattern.search(html):
        html = pattern.sub(f"<title>{title}</title>", html, count=1)
    else:
        head_close = re.compile(r"</head>", re.IGNORECASE)
        if head_close.search(html):
            html = head_close.sub(f"<title>{title}</title></head>", html, count=1)
        else:
            html = f"<head><title>{title}</title></head>" + html

    if html != before:
        bak = static_dir / "index.html.bak"
        if not bak.exists():
            try:
                bak.write_text(before, encoding="utf-8", errors="ignore")
            except Exception:
                pass
        index_file.write_text(html, encoding="utf-8")


# 根路径直接返回前端 index.html（200）。如文件不存在，回退到 /app/ 重定向。
@app.get("/", include_in_schema=False)
async def serve_root_index():
    index_file = Path(settings.WEBAPP_STATIC_DIR).absolute() / "index.html"
    if index_file.exists():
        try:
            html = index_file.read_text(encoding="utf-8", errors="ignore")
            title_override = _get_title_override()
            if title_override:
                # 替换现有 <title>... </title>
                pattern = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
                if pattern.search(html):
                    html = pattern.sub(f"<title>{title_override}</title>", html, count=1)
                else:
                    # 若缺失 <title>，则在 </head> 前插入
                    head_close = re.compile(r"</head>", re.IGNORECASE)
                    if head_close.search(html):
                        html = head_close.sub(
                            f"<title>{title_override}</title></head>", html, count=1
                        )
                    else:
                        # 无 head，直接前置一个最简单的 head+title
                        html = f"<head><title>{title_override}</title></head>" + html

                # 为防止前端 JS 覆盖，再追加运行时强制设置 document.title 的脚本
                _esc = (
                    str(title_override)
                    .replace("\\", "\\\\")
                    .replace("'", "\\'")
                )
                override_script = (
                    "<script>(function(){var t='" + _esc + "';"
                    "function setTitle(){try{document.title=t;}catch(e){}}"
                    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded', setTitle);}else{setTitle();}"
                    "window.addEventListener('load', setTitle);})();</script>"
                )
                head_close = re.compile(r"</head>", re.IGNORECASE)
                if head_close.search(html):
                    html = head_close.sub(override_script + "</head>", html, count=1)
                else:
                    html = "<head>" + override_script + "</head>" + html
            return Response(
                content=html,
                media_type="text/html",
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
        except Exception as e:
            logger.error(f"读取或处理 index.html 失败: {e}")
            # 兜底直接返回文件
            return FileResponse(str(index_file))
    return RedirectResponse(url="/app/")


@app.get("/app/", include_in_schema=False)
async def serve_app_index():
    # 与根路径相同的动态标题注入逻辑，覆盖静态挂载对 /app/ 的默认返回
    index_file = Path(settings.WEBAPP_STATIC_DIR).absolute() / "index.html"
    if index_file.exists():
        try:
            html = index_file.read_text(encoding="utf-8", errors="ignore")
            title_override = _get_title_override()
            if title_override:
                pattern = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
                if pattern.search(html):
                    html = pattern.sub(f"<title>{title_override}</title>", html, count=1)
                else:
                    head_close = re.compile(r"</head>", re.IGNORECASE)
                    if head_close.search(html):
                        html = head_close.sub(
                            f"<title>{title_override}</title></head>", html, count=1
                        )
                    else:
                        html = f"<head><title>{title_override}</title></head>" + html

                _esc = (
                    str(title_override)
                    .replace("\\", "\\\\")
                    .replace("'", "\\'")
                )
                override_script = (
                    "<script>(function(){var t='" + _esc + "';"
                    "function setTitle(){try{document.title=t;}catch(e){}}"
                    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded', setTitle);}else{setTitle();}"
                    "window.addEventListener('load', setTitle);})();</script>"
                )
                head_close = re.compile(r"</head>", re.IGNORECASE)
                if head_close.search(html):
                    html = head_close.sub(override_script + "</head>", html, count=1)
                else:
                    html = "<head>" + override_script + "</head>" + html
            return Response(content=html, media_type="text/html")
        except Exception as e:
            logger.error(f"读取或处理 index.html 失败: {e}")
            return FileResponse(str(index_file))
    return RedirectResponse(url="/app/")


@app.head("/", include_in_schema=False)
async def root_head_ok():
    # 允许对根路径发起 HEAD 探测，返回 200
    return Response(status_code=200)


# 兼容 /app 无斜杠访问，复用相同逻辑
@app.get("/app", include_in_schema=False)
async def serve_app_index_no_slash():
    return await serve_app_index()
