"""Chroma 向量索引构建与更新"""
import logging
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from .parser import SkillMeta, SkillParser
from skillsbrain.config import settings
from .subscriptions import Subscription, SubscriptionStore

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
        self._subscription_store = SubscriptionStore()
        self._subscriptions: dict[str, Subscription] = {"local": Subscription(name="local", root=str(self.skills_dir), enabled=True)}
        for sub in self._subscription_store.load():
            self._subscriptions[sub.name] = sub
        self._watchers: dict[str, object] = {}
        self._watcher_stops: dict[str, callable] = {}

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
            "source_type": "local",
            "source_name": "local",
            "source_root": str(self.skills_dir),
            "source_rel_path": skill.relative_path,
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

    def _upsert(self, skills: list[SkillMeta], source_name: str = "local", source_root: str | None = None):
        if not skills:
            return

        texts = [self._build_text(s) for s in skills]
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        ids = [f"{source_name}:{s.skill_id}" for s in skills]
        metadatas = []
        for s in skills:
            meta = self._metadata_from_skill(s)
            meta["source_type"] = "subscribed" if source_name != "local" else "local"
            meta["source_name"] = source_name
            meta["source_root"] = source_root or str(self.skills_dir)
            meta["source_rel_path"] = s.relative_path
            meta["skill_id"] = f"{source_name}:{s.skill_id}"
            metadatas.append(meta)

        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
        logger.info("Upserted %d skills into index for source=%s.", len(skills), source_name)

    def _collect_skills_from_root(self, root: Path) -> list[SkillMeta]:
        parser = SkillParser(root)
        skills = []
        for md_file in root.rglob("SKILL.md"):
            skill = parser.parse(md_file)
            if skill:
                skills.append(skill)
        return skills

    def _sync_source(self, source_name: str, root: Path) -> int:
        root = Path(root).resolve()
        skills = self._collect_skills_from_root(root)
        prefix = f"{source_name}:"
        existing = self._collection.get(include=[], where={"source_name": source_name})
        existing_ids = set(existing.get("ids", []))
        current_ids = {f"{source_name}:{skill.skill_id}" for skill in skills}
        stale_ids = sorted(existing_ids - current_ids)
        if stale_ids:
            self._delete_ids(stale_ids)
        self._upsert(skills, source_name=source_name, source_root=str(root))
        logger.info("Synced source %s: %d skills, %d stale removed.", source_name, len(skills), len(stale_ids))
        return len(skills)

    def full_sync(self) -> int:
        total = self._sync_source("local", self.skills_dir)
        for sub in self._subscription_store.load():
            if sub.enabled:
                total += self._sync_source(sub.name, Path(sub.root))
        return total

    def sync_subscription(self, name: str) -> int:
        sub = self._subscription_store.get(name)
        if not sub:
            raise ValueError(f"Subscription '{name}' not found")
        return self._sync_source(sub.name, Path(sub.root))

    def register_watcher(self, source_name: str, observer: object, stop_callback=None):
        if source_name in self._watchers:
            self.stop_watcher(source_name)
        self._watchers[source_name] = observer
        if stop_callback is not None:
            self._watcher_stops[source_name] = stop_callback

    def stop_watcher(self, source_name: str):
        observer = self._watchers.pop(source_name, None)
        stop_callback = self._watcher_stops.pop(source_name, None)
        if stop_callback is not None:
            stop_callback(observer)

    def stop_all_watchers(self):
        for source_name in list(self._watchers.keys()):
            self.stop_watcher(source_name)

    def subscribe_source(self, root: Path, name: str | None = None) -> dict:
        root = Path(root).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Invalid subscription root: {root}")
        source_name = name or root.name
        sub = Subscription(name=source_name, root=str(root), enabled=True)
        self._subscription_store.add(sub)
        self._subscriptions[source_name] = sub
        count = self._sync_source(source_name, root)
        return {"name": source_name, "root": str(root), "indexed": count}

    def unsubscribe_source(self, name_or_root: str) -> dict:
        sub = self._subscription_store.get(name_or_root)
        if sub is None:
            for item in self._subscription_store.load():
                if Path(item.root).resolve() == Path(name_or_root).resolve():
                    sub = item
                    break
        if sub is None:
            raise ValueError(f"Subscription '{name_or_root}' not found")

        self.stop_watcher(sub.name)
        removed_ids = self._collection.get(include=[], where={"source_name": sub.name}).get("ids", [])
        if removed_ids:
            self._delete_ids(removed_ids)
        self._subscription_store.remove(sub.name)
        self._subscriptions.pop(sub.name, None)
        return {"name": sub.name, "root": sub.root, "removed": len(removed_ids)}

    def list_subscriptions(self) -> list[dict]:
        return [item.to_dict() for item in self._subscription_store.load()]

    def update_skill(self, file_path: Path):
        try:
            skill_id = self._skill_id_from_path(file_path)
        except Exception:
            logger.exception("Failed to resolve skill id for path: %s", file_path)
            return

        skill = self._parser.parse(file_path)
        if skill:
            self._upsert([skill], source_name="local", source_root=str(self.skills_dir))
        else:
            try:
                self._delete_ids([f"local:{skill_id}"])
            except Exception:
                logger.exception("Failed to remove invalid skill from index: %s", file_path)

    def delete_skill(self, file_path: Path):
        try:
            skill_id = self._skill_id_from_path(file_path)
            self._delete_ids([f"local:{skill_id}"])
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
