"""FastAPI 应用。"""

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from skillsbrain.config import settings
from skillsbrain.core.engine import SkillEngine
from skillsbrain.core.indexer import SkillIndexer
from skillsbrain.core.watcher import start_watcher, stop_watcher
from skillsbrain.runtime import SERVICE_NAME, now_iso, write_runtime_file
from skillsbrain.utils.call_logger import call_logger


def create_app(
    skills_dir: Path | None = None,
    index_dir: Path | None = None,
    runtime_file: Path | None = None,
    runtime_metadata: dict | None = None,
    shutdown_token: str | None = None,
) -> FastAPI:
    """创建 FastAPI 应用。"""

    resolved_skills_dir = (skills_dir or Path(settings.skills_dir)).resolve()
    resolved_index_dir = (index_dir or Path(settings.index_dir)).resolve()
    log_dir = Path(settings.log_dir).resolve()
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
        title=SERVICE_NAME,
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
    app.state.server = None
    app.state.shutdown_token = shutdown_token
    app.state.runtime_file = runtime_file
    app.state.runtime = {
        "service": SERVICE_NAME,
        "pid": None,
        "host": None,
        "port": None,
        "data_dir": None,
        "skills_dir": str(resolved_skills_dir),
        "index_dir": str(resolved_index_dir),
        "log_dir": str(log_dir),
        "started_at": None,
        "ready_at": None,
        "status": "starting",
        "ready": False,
    }
    if runtime_metadata:
        app.state.runtime.update(runtime_metadata)

    def persist_runtime(status: str, ready: bool) -> None:
        app.state.runtime["status"] = status
        app.state.runtime["ready"] = ready
        app.state.runtime["pid"] = os.getpid()
        if app.state.runtime_file is None:
            return
        payload = dict(app.state.runtime)
        payload["updated_at"] = now_iso()
        write_runtime_file(app.state.runtime_file, payload)

    def public_runtime() -> dict:
        runtime = dict(app.state.runtime)
        runtime.pop("shutdown_token", None)
        return runtime

    @app.on_event("startup")
    def startup() -> None:
        logger.info("SkillsBrain starting...")
        if not app.state.runtime.get("started_at"):
            app.state.runtime["started_at"] = now_iso()
        persist_runtime(status="starting", ready=False)

        app.state.indexer = SkillIndexer(
            skills_dir=resolved_skills_dir,
            index_dir=resolved_index_dir,
        )
        app.state.engine = SkillEngine(app.state.indexer)

        count = app.state.indexer.full_sync()
        logger.info("Indexed %s skills", count)

        app.state.observer = start_watcher(app.state.indexer)
        for sub in app.state.indexer.list_subscriptions():
            if sub["name"] == "local":
                continue
            observer = start_watcher(app.state.indexer, root=Path(sub["root"]), source_name=sub["name"])
            app.state.indexer.register_watcher(sub["name"], observer, stop_callback=stop_watcher)

        app.state.ready = True
        app.state.runtime["ready_at"] = now_iso()
        persist_runtime(status="ready", ready=True)
        logger.info("SkillsBrain ready")

    @app.on_event("shutdown")
    def shutdown() -> None:
        app.state.ready = False
        persist_runtime(status="stopping", ready=False)
        if app.state.indexer is not None:
            app.state.indexer.stop_all_watchers()
        stop_watcher(app.state.observer)

    class MatchRequest(BaseModel):
        query: str = Field(..., description="自然语言查询")
        agent_type: Optional[str] = Field(None, description="claude_code | codex")
        session_id: Optional[str] = Field(None, description="会话 ID")
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

    class ShutdownRequest(BaseModel):
        token: str = Field(..., description="关闭服务令牌")

    @app.post("/api/skill/match", response_model=list[SkillInfo])
    def match_skill(req: MatchRequest) -> list[SkillInfo]:
        start_time = time.time()

        results = app.state.engine.match(
            query=req.query,
            agent_type=req.agent_type,
            top_k=req.top_k,
        )

        skills = []
        for result in results:
            skills.append(
                SkillInfo(
                    skill_id=result["skill_id"],
                    name=result["name"],
                    description=result["description"],
                    compatibility=[item for item in result.get("compatibility", "").split(",") if item],
                    tags=[item for item in result.get("tags", "").split(",") if item],
                    version=result.get("version", "1.0.0"),
                    author=result.get("author", ""),
                    enabled=result.get("enabled", "True").lower() == "true",
                    created_at=result.get("created_at", ""),
                    file_path=result.get("file_path", ""),
                    relative_path=result.get("relative_path", ""),
                    source_type=result.get("source_type", "local"),
                    source_name=result.get("source_name", "local"),
                    source_root=result.get("source_root", ""),
                    source_rel_path=result.get("source_rel_path", ""),
                    score=result["score"],
                )
            )

        latency_ms = (time.time() - start_time) * 1000
        call_logger.log(
            query=req.query,
            hits=[skill.model_dump() for skill in skills],
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
    ) -> dict:
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
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc
        return {"total": total, "offset": offset, "limit": limit, "skills": skills}

    @app.get("/api/skill/detail/{name}")
    def get_skill(name: str) -> dict:
        try:
            result = app.state.indexer.get_skill(name)
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

        if not result:
            raise HTTPException(404, f"Skill '{name}' not found")
        return result

    @app.post("/api/skill/reindex")
    def reindex() -> dict:
        count = app.state.indexer.full_sync()
        return {"indexed": count, "message": "Reindex complete"}

    @app.get("/api/skill/stats")
    def stats() -> dict:
        return app.state.indexer.get_stats()

    @app.get("/api/source/list")
    def source_list() -> dict:
        return {"sources": app.state.indexer.list_subscriptions()}

    @app.post("/api/source/subscribe")
    def source_subscribe(req: SubscribeRequest) -> dict:
        try:
            return app.state.indexer.subscribe_source(Path(req.path), name=req.name)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/source/unsubscribe")
    def source_unsubscribe(req: UnsubscribeRequest) -> dict:
        try:
            return app.state.indexer.unsubscribe_source(req.name_or_root)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict:
        if not app.state.ready or app.state.indexer is None or app.state.engine is None:
            raise HTTPException(503, "service not ready")
        return {"status": "ready"}

    @app.get("/api/admin/status")
    def admin_status() -> dict:
        return public_runtime()

    @app.post("/api/admin/shutdown")
    def admin_shutdown(req: ShutdownRequest) -> dict:
        if req.token != app.state.shutdown_token:
            raise HTTPException(403, "invalid shutdown token")

        server = getattr(app.state, "server", None)
        if server is None:
            raise HTTPException(503, "server controller unavailable")

        def _shutdown_later() -> None:
            time.sleep(0.1)
            server.should_exit = True

        threading.Thread(target=_shutdown_later, daemon=True).start()
        return {"status": "stopping"}

    return app
