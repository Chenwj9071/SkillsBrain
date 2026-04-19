"""FastAPI 主入口"""
import logging
import sys
from pathlib import Path

# 让 api/ 运行时能找到同级的 core/ utils/ 等模块
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载配置（会设置 HF_ENDPOINT 等环境变量）
import config  # noqa: F401

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import time

from utils.call_logger import call_logger

# ── 日志 ────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "skill_center.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── 延迟初始化核心模块（启动时做全量同步） ──────────────────────────
from core.indexer import SkillIndexer
from core.engine import SkillEngine
from core.watcher import start_watcher

app = FastAPI(title="SkillsBrain", version="1.0.0", description="本地技能路由引擎")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局单例 ───────────────────────────────────────────────────────
indexer: Optional[SkillIndexer] = None
engine: Optional[SkillEngine] = None


@app.on_event("startup")
def startup():
    global indexer, engine
    logger.info("SkillsBrain 启动中...")
    indexer = SkillIndexer()
    engine = SkillEngine(indexer)

    count = indexer.full_sync()
    logger.info(f"全量同步完成: {count} 个技能已索引")

    start_watcher(indexer)
    logger.info("SkillsBrain 已就绪 ✓")


# ── Request/Response 模型 ────────────────────────────────────────────
class MatchRequest(BaseModel):
    query: str = Field(..., description="自然语言查询")
    agent_type: Optional[str] = Field(None, description="claude_code | codex")
    session_id: Optional[str] = Field(None, description="调用方会话ID，用于追踪")
    top_k: int = Field(5, ge=1, le=20)


class SkillInfo(BaseModel):
    name: str
    description: str
    compatibility: list[str]
    tags: list[str]
    version: str
    author: str
    enabled: bool
    created_at: str
    file_path: str
    score: float


# ── API 接口 ───────────────────────────────────────────────────────

@app.post("/api/skill/match", response_model=list[SkillInfo])
def match_skill(req: MatchRequest, http_req: Request = None):
    """语义检索最匹配技能（Agent 主调用入口）"""
    start_time = time.time()
    
    results = engine.match(
        query=req.query,
        agent_type=req.agent_type,
        top_k=req.top_k,
    )
    
    skills = []
    for r in results:
        skills.append(SkillInfo(
            name=r["name"],
            description=r["description"],
            compatibility=r.get("compatibility", "").split(","),
            tags=r.get("tags", "").split(","),
            version=r.get("version", "1.0.0"),
            author=r.get("author", ""),
            enabled=r.get("enabled", "True").lower() == "true",
            created_at=r.get("created_at", ""),
            file_path=r.get("file_path", ""),
            score=r["score"],
        ))
    
    # 记录调用日志
    latency_ms = (time.time() - start_time) * 1000
    call_logger.log(
        query=req.query,
        hits=[s.model_dump() for s in skills],
        source=req.agent_type,
        session_id=req.session_id,
        top_k=req.top_k,
        latency_ms=latency_ms,
    )
    
    return skills


@app.get("/api/skill/list")
def list_skills(agent_type: Optional[str] = None, enabled_only: bool = True):
    """列出所有技能（管理接口）"""
    try:
        all_data = indexer._collection.get(
            include=["metadatas"],
        )
    except Exception as e:
        raise HTTPException(500, str(e))

    skills = []
    for meta in all_data["metadatas"]:
        compat = meta.get("compatibility", "").split(",")
        if agent_type and agent_type not in compat:
            continue
        if enabled_only and meta.get("enabled", "True").lower() != "true":
            continue
        skills.append(meta)
    return {"total": len(skills), "skills": skills}


@app.get("/api/skill/detail/{name}")
def get_skill(name: str):
    """查看单个技能详情"""
    try:
        result = indexer._collection.get(ids=[name], include=["metadatas"])
    except Exception as e:
        raise HTTPException(500, str(e))

    if not result["metadatas"]:
        raise HTTPException(404, f"技能 '{name}' 不存在")
    return result["metadatas"][0]


@app.post("/api/skill/enable/{name}")
def toggle_skill(name: str, enabled: bool = True):
    """上下线技能（更新 enabled 字段并重新索引）"""
    try:
        result = indexer._collection.get(ids=[name], include=["metadatas"])
    except Exception as e:
        raise HTTPException(500, str(e))

    if not result["metadatas"]:
        raise HTTPException(404, f"技能 '{name}' 不存在")

    meta = result["metadatas"][0].copy()
    meta["enabled"] = str(enabled).lower()

    # 取出 embedding 重新 upsert
    emb_result = indexer._collection.get(ids=[name], include=["embeddings"])
    if emb_result["embeddings"]:
        indexer._collection.upsert(
            ids=[name],
            embeddings=emb_result["embeddings"],
            metadatas=[meta],
        )
    return {"name": name, "enabled": enabled}


@app.post("/api/skill/reindex")
def reindex():
    """手动触发全量重建索引"""
    count = indexer.full_sync()
    return {"indexed": count, "message": "全量重建完成"}


@app.get("/api/skill/stats")
def stats():
    """索引统计"""
    return indexer.get_stats()


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
