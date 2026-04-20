"""FastAPI 应用"""
import logging
import sys
from pathlib import Path
from typing import Optional

import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from skillsbrain.config import settings
from skillsbrain.core.indexer import SkillIndexer
from skillsbrain.core.engine import SkillEngine
from skillsbrain.core.watcher import start_watcher, stop_watcher
from skillsbrain.utils.call_logger import call_logger


def create_app(skills_dir: Path = None, index_dir: Path = None) -> FastAPI:
    """创建 FastAPI 应用"""

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

    cors_origins = settings.cors_origin_list or ["http://127.0.0.1", "http://localhost"]
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.indexer = None
    app.state.engine = None
    app.state.observer = None
    app.state.ready = False

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

        app.state.observer = start_watcher(app.state.indexer)
        app.state.ready = True
        logger.info("SkillsBrain ready")

        for sub in app.state.indexer.list_subscriptions():
            if sub["name"] == "local":
                continue
            observer = start_watcher(app.state.indexer, root=Path(sub["root"]), source_name=sub["name"])
            app.state.indexer.register_watcher(sub["name"], observer, stop_callback=stop_watcher)

    @app.on_event("shutdown")
    def shutdown():
        app.state.indexer.stop_all_watchers()
        stop_watcher(app.state.observer)

    class MatchRequest(BaseModel):
        query: str = Field(..., description="自然语言查询")
        agent_type: Optional[str] = Field(None, description="claude_code | codex")
        session_id: Optional[str] = Field(None, description="会话ID")
        top_k: int = Field(5, ge=1, le=20)

    class SkillInfo(BaseModel):
        skill_id: str
        name: str
        description: str
        compatibility: list[str]
        tags: list[str]
        version: str
        author: str
        enabled: bool
        created_at: str
        file_path: str
        relative_path: str
        source_type: str
        source_name: str
        source_root: str
        source_rel_path: str
        score: float

    class SubscribeRequest(BaseModel):
        path: str
        name: Optional[str] = None

    class UnsubscribeRequest(BaseModel):
        name_or_root: str

    @app.post("/api/skill/match", response_model=list[SkillInfo])
    def match_skill(req: MatchRequest):
        start_time = time.time()

        results = app.state.engine.match(
            query=req.query,
            agent_type=req.agent_type,
            top_k=req.top_k,
        )

        skills = []
        for r in results:
            skills.append(SkillInfo(
                skill_id=r["skill_id"],
                name=r["name"],
                description=r["description"],
                compatibility=[item for item in r.get("compatibility", "").split(",") if item],
                tags=[item for item in r.get("tags", "").split(",") if item],
                version=r.get("version", "1.0.0"),
                author=r.get("author", ""),
                enabled=r.get("enabled", "True").lower() == "true",
                created_at=r.get("created_at", ""),
                file_path=r.get("file_path", ""),
                relative_path=r.get("relative_path", ""),
                source_type=r.get("source_type", "local"),
                source_name=r.get("source_name", "local"),
                source_root=r.get("source_root", ""),
                source_rel_path=r.get("source_rel_path", ""),
                score=r["score"],
            ))

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
    def list_skills(
        agent_type: Optional[str] = None,
        enabled_only: bool = True,
        offset: int = 0,
        limit: int = 50,
    ):
        if offset < 0:
            raise HTTPException(400, "offset must be >= 0")
        if limit < 1 or limit > 200:
            raise HTTPException(400, "limit must be between 1 and 200")

        try:
            skills, total = app.state.indexer.list_skills(
                agent_type=agent_type,
                enabled_only=enabled_only,
                offset=offset,
                limit=limit,
            )
        except Exception as e:
            raise HTTPException(500, str(e))
        return {"total": total, "offset": offset, "limit": limit, "skills": skills}

    @app.get("/api/skill/detail/{name}")
    def get_skill(name: str):
        try:
            result = app.state.indexer.get_skill(name)
        except Exception as e:
            raise HTTPException(500, str(e))

        if not result:
            raise HTTPException(404, f"Skill '{name}' not found")
        return result

    @app.post("/api/skill/reindex")
    def reindex():
        count = app.state.indexer.full_sync()
        return {"indexed": count, "message": "Reindex complete"}

    @app.get("/api/skill/stats")
    def stats():
        return app.state.indexer.get_stats()

    @app.get("/api/source/list")
    def source_list():
        return {"sources": app.state.indexer.list_subscriptions()}

    @app.post("/api/source/subscribe")
    def source_subscribe(req: SubscribeRequest):
        try:
            return app.state.indexer.subscribe_source(Path(req.path), name=req.name)
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.post("/api/source/unsubscribe")
    def source_unsubscribe(req: UnsubscribeRequest):
        try:
            return app.state.indexer.unsubscribe_source(req.name_or_root)
        except Exception as e:
            raise HTTPException(400, str(e))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        if not app.state.ready or app.state.indexer is None or app.state.engine is None:
            raise HTTPException(503, "service not ready")
        return {"status": "ready"}

    return app
