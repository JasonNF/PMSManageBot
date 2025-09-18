"""
应用包初始化：
- 确保首次启动时数据库表存在（如不存在则创建）
"""
from app.config import settings
from app.db import DB
from app.log import logger
from pathlib import Path


def _ensure_db():
    try:
        db_path = settings.DATA_PATH / "data.db"
        if not db_path.exists():
            logger.info(f"初始化数据库: {db_path}")
            DB().create_table()
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")


_ensure_db()
