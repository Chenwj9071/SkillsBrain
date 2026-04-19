"""Chroma 向量索引构建与更新"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from pathlib import Path
import logging

from .parser import SkillMeta, SkillParser
from config import settings, INDEX_DIR, SKILLS_DIR

logger = logging.getLogger(__name__)


class SkillIndexer:
    def __init__(self):
        self._model = None
        self._client = chromadb.PersistentClient(
            path=str(INDEX_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="skills",
            metadata={"hnsw:space": "cosine"},
        )
        self._parser = SkillParser()

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {settings.embedding_model}")
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info("Embedding model loaded.")
        return self._model

    def _build_text(self, skill: SkillMeta) -> str:
        parts = [skill.name, skill.description]
        if skill.tags:
            parts.extend(skill.tags)
        return " | ".join(parts)

    def _upsert(self, skills: list[SkillMeta]):
        if not skills:
            return

        texts = [self._build_text(s) for s in skills]
        embeddings = self.model.encode(texts, normalize_embeddings=True)

        ids = [s.name for s in skills]
        metadatas = [
            {
                "name": s.name,
                "description": s.description,
                "compatibility": ",".join(s.compatibility),
                "tags": ",".join(s.tags),
                "version": s.version,
                "author": s.author,
                "enabled": str(s.enabled),
                "created_at": s.created_at,
                "file_path": s.file_path,
            }
            for s in skills
        ]

        self._collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas)
        logger.info(f"Upserted {len(skills)} skills into index.")

    def full_sync(self) -> int:
        """全量扫描 skills/ 目录，同步所有技能到索引"""
        count = 0
        skills = []
        for md_file in SKILLS_DIR.rglob("SKILL.md"):
            skill = self._parser.parse(md_file)
            if skill:
                skills.append(skill)
                count += 1

        if skills:
            self._upsert(skills)
        logger.info(f"Full sync done: {count} skills indexed.")
        return count

    def update_skill(self, file_path: Path):
        skill = self._parser.parse(file_path)
        if skill:
            self._upsert([skill])
        else:
            # 解析失败 → 从索引中删除该条目
            name = file_path.stem
            try:
                self._collection.delete(ids=[name])
            except Exception:
                pass

    def delete_skill(self, file_path: Path):
        name = file_path.stem
        try:
            self._collection.delete(ids=[name])
            logger.info(f"Removed skill '{name}' from index.")
        except Exception:
            pass

    def get_stats(self) -> dict:
        return {
            "total": self._collection.count(),
            "model": settings.embedding_model,
        }
