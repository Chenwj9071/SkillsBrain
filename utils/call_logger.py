"""技能调用日志记录器

按天归档，JSONL 格式，独立于系统日志。
每条记录包含：时间戳、来源、会话ID、请求内容、命中情况、延迟。
"""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import threading

# 项目根目录
BASE_DIR = Path(__file__).parent.parent
CALL_LOG_DIR = BASE_DIR / "logs" / "calls"

# 东八区
SHANGHAI_TZ = timezone(timedelta(hours=8))


class CallLogger:
    """线程安全的调用日志记录器，按天归档到 JSONL 文件"""

    def __init__(self):
        self._lock = threading.Lock()
        CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _today_file(self) -> Path:
        date_str = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d")
        return CALL_LOG_DIR / f"{date_str}.jsonl"

    def log(
        self,
        query: str,
        hits: list[dict],
        source: Optional[str] = None,
        session_id: Optional[str] = None,
        top_k: int = 5,
        latency_ms: float = 0,
    ):
        """记录一次技能检索调用"""
        record = {
            "timestamp": datetime.now(SHANGHAI_TZ).isoformat(),
            "source": source or "unknown",
            "session_id": session_id or "",
            "query": query,
            "top_k": top_k,
            "hit_count": len(hits),
            "hits": [
                {"name": h.get("name"), "score": h.get("score")}
                for h in hits
            ],
            "latency_ms": round(latency_ms, 2),
        }

        line = json.dumps(record, ensure_ascii=False)

        with self._lock:
            file = self._today_file()
            with open(file, "a", encoding="utf-8") as f:
                f.write(line + "\n")


# 全局单例
call_logger = CallLogger()
