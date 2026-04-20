"""Chroma 向量索引构建与更新"""
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from .parser import SkillMeta, SkillParser
from skillsbrain.config import settings

logger = logging.getLogger(__name__)


class SkillIndexer:
    def __init__(self, skills_dir: Path = None, index_dir: Path = None):
        self.skills_dir = Path(skills_dir or settings.skills_dir).resolve()
        self.index_dir = Path(index_dir or settings.index_dir).resolve()
        self._model = None
        self._client = chromadb.PersistentClient(
            path=str(self.index_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="skills",
            metadata={"hnsw:space": "cosine"},
        )
        self._parser = SkillParser(self.skills_dir)

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model} on device: {settings.device}")
            self._model = SentenceTransformer(settings.embedding_model, device=settings.device)
            logger.info("Embedding model loaded.")
        return self._model

    def _build_text(self, skill: SkillMeta) -> str:
        parts = [skill.name, skill.description]
        if skill.tags:
            parts.extend(skill.tags)
        return " | ".join(parts)

    def _metadata_from_skill(self, skill: SkillMeta) -> dict:
        return {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "description": skill.description,
            "compatibility": ",".join(skill.compatibility),
            "tags": ",".join(skill.tags),
            "version": skill.version,
            "author": skill.author,
            "enabled": str(skill.enabled),
            "created_at": skill.created_at,
            "file_path": skill.file_path,
            "relative_path": skill.relative_path,
        }

    def _skill_id_from_path(self, file_path: Path) -> str:
        resolved_path = Path(file_path).resolve()
        relative_path = resolved_path.relative_to(self.skills_dir)
        if relative_path.name == "SKILL.md" and relative_path.parent != Path("."):
            return relative_path.parent.as_posix()
        return relative_path.as_posix()

    def _delete_ids(self, skill_ids: list[str]):
        if not skill_ids:
            return
        self._collection.delete(ids=skill_ids)
        logger.info("Removed %d skills from index.", len(skill_ids))

    @staticmethod
    def _normalize_metadata(meta: dict) -> dict:
        data = dict(meta)
        data["compatibility"] = [item for item in (data.get("compatibility", "") or "").split(",") if item]
        data["tags"] = [item for item in (data.get("tags", "") or "").split(",") if item]
        data["enabled"] = str(data.get("enabled", "True")).lower() == "true"
        return data

    def _upsert(self, skills: list[SkillMeta]):
        if not skills:
            return

        texts = [self._build_text(s) for s in skills]
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        ids = [s.skill_id for s in skills]
        metadatas = [self._metadata_from_skill(s) for s in skills]

        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
        logger.info(f"Upserted {len(skills)} skills into index.")

    def full_sync(self) -> int:
        """全量扫描 skills/ 目录，同步所有技能到索引，并清理陈旧数据"""
        skills = []
        current_ids = set()

        for md_file in self.skills_dir.rglob("SKILL.md"):
            skill = self._parser.parse(md_file)
            if skill:
                skills.append(skill)
                current_ids.add(skill.skill_id)

        existing = self._collection.get(include=[])
        existing_ids = set(existing.get("ids", []))
        stale_ids = sorted(existing_ids - current_ids)
        if stale_ids:
            self._delete_ids(stale_ids)

        self._upsert(skills)
        logger.info("Full sync done: %d skills indexed, %d stale removed.", len(skills), len(stale_ids))
        return len(skills)

    def update_skill(self, file_path: Path):
        try:
            skill_id = self._skill_id_from_path(file_path)
        except Exception:
            logger.exception("Failed to resolve skill id for path: %s", file_path)
            return

        skill = self._parser.parse(file_path)
        if skill:
            self._upsert([skill])
        else:
            try:
                self._delete_ids([skill_id])
            except Exception:
                logger.exception("Failed to remove invalid skill from index: %s", file_path)

    def delete_skill(self, file_path: Path):
        try:
            skill_id = self._skill_id_from_path(file_path)
            self._delete_ids([skill_id])
            logger.info("Removed skill '%s' from index.", skill_id)
        except Exception:
            logger.exception("Failed to delete skill for path: %s", file_path)

    def query_skills(self, query: str, top_k: int) -> list[dict]:
        emb = self.model.encode([query], normalize_embeddings=True)
        hits = self._collection.query(
            query_embeddings=emb,
            n_results=top_k,
            include=["metadatas", "distances"],
        )

        results = []
        for i, meta in enumerate(hits["metadatas"][0]):
            dist = hits["distances"][0][i]
            score = round(1 - dist, 4)
            results.append({**meta, "score": score})
        return results

    def list_skills(
        self,
        agent_type: str | None = None,
        enabled_only: bool = True,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[dict], int]:
        data = self._collection.get(include=["metadatas"])
        skills = []
        for meta in data.get("metadatas", []):
            normalized = self._normalize_metadata(meta)
            if agent_type and agent_type not in normalized["compatibility"]:
                continue
            if enabled_only and not normalized["enabled"]:
                continue
            skills.append(normalized)

        skills.sort(key=lambda item: item.get("skill_id", item.get("name", "")))
        total = len(skills)
        if limit is None:
            return skills[offset:], total
        return skills[offset: offset + limit], total

    def get_skill(self, skill_id: str) -> dict | None:
        result = self._collection.get(ids=[skill_id], include=["metadatas"])
        metadatas = result.get("metadatas", [])
        if not metadatas:
            return None
        return self._normalize_metadata(metadatas[0])

    def get_stats(self) -> dict:
        return {
            "total": self._collection.count(),
            "model": settings.embedding_model,
        }
