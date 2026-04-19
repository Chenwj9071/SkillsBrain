"""FastAPI 应用"""
import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import time

from skillsbrain.config import settings
from skillsbrain.core.indexer import SkillIndexer
from skillsbrain.core.engine import SkillEngine
from skillsbrain.core.watcher import start_watcher
from skillsbrain.utils.call_logger import call_logger


def create_app(skills_dir: Path = None, index_dir: Path = None) -> FastAPI:
    """创建 FastAPI 应用"""
    
    # 日志配置
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "skillsbrain.log", encoding="utf-8"),
        ],
    )
    logger = logging.getLogger(__name__)

    app = FastAPI(
        title="SkillsBrain",
        version="1.0.0",
        description="Local skill routing engine for AI Agents",
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局状态
    app.state.indexer = None
    app.state.engine = None

    @app.on_event("startup")
    def startup():
        logger.info("SkillsBrain starting...")
        
        app.state.indexer = SkillIndexer(
            skills_dir=skills_dir or Path(settings.skills_dir),
            index_dir=index_dir or Path(settings.index_dir),
        )
        app.state.engine = SkillEngine(app.state.indexer)

        count = app.state.indexer.full_sync()
        logger.info(f"Indexed {count} skills")

        start_watcher(app.state.indexer)
        logger.info("SkillsBrain ready")

    # Request/Response 模型
    class MatchRequest(BaseModel):
        query: str = Field(..., description="自然语言查询")
        agent_type: Optional[str] = Field(None, description="claude_code | codex")
        session_id: Optional[str] = Field(None, description="会话ID")
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

    # API 接口
    @app.post("/api/skill/match", response_model=list[SkillInfo])
    def match_skill(req: MatchRequest):
        """语义检索最匹配技能"""
        start_time = time.time()
        
        results = app.state.engine.match(
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
        """列出所有技能"""
        try:
            all_data = app.state.indexer._collection.get(include=["metadatas"])
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
            result = app.state.indexer._collection.get(ids=[name], include=["metadatas"])
        except Exception as e:
            raise HTTPException(500, str(e))

        if not result["metadatas"]:
            raise HTTPException(404, f"Skill '{name}' not found")
        return result["metadatas"][0]

    @app.post("/api/skill/enable/{name}")
    def toggle_skill(name: str, enabled: bool = True):
        """上下线技能"""
        try:
            result = app.state.indexer._collection.get(ids=[name], include=["metadatas"])
        except Exception as e:
            raise HTTPException(500, str(e))

        if not result["metadatas"]:
            raise HTTPException(404, f"Skill '{name}' not found")

        meta = result["metadatas"][0].copy()
        meta["enabled"] = str(enabled).lower()

        emb_result = app.state.indexer._collection.get(ids=[name], include=["embeddings"])
        if emb_result["embeddings"]:
            app.state.indexer._collection.upsert(
                ids=[name],
                embeddings=emb_result["embeddings"],
                metadatas=[meta],
            )
        return {"name": name, "enabled": enabled}

    @app.post("/api/skill/reindex")
    def reindex():
        """重建索引"""
        count = app.state.indexer.full_sync()
        return {"indexed": count, "message": "Reindex complete"}

    @app.get("/api/skill/stats")
    def stats():
        """索引统计"""
        return app.state.indexer.get_stats()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
