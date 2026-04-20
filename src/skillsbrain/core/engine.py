"""三层检索引擎"""
import logging
from typing import Optional
from .indexer import SkillIndexer
from skillsbrain.config import settings

logger = logging.getLogger(__name__)


class SkillEngine:
    def __init__(self, indexer: SkillIndexer):
        self._indexer = indexer

    # ── 第一层：快速过滤 ──────────────────────────────────────────────
    def _filter_by_metadata(
        self,
        results: list[dict],
        agent_type: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[dict]:
        """按元数据过滤候选"""
        filtered = []
        for r in results:
            compat = (r.get("compatibility") or "").split(",")
            compat = [c.strip() for c in compat if c.strip()]

            if enabled_only and r.get("enabled", "True").lower() != "true":
                continue
            if agent_type and agent_type not in compat:
                continue

            filtered.append(r)
        return filtered

    # ── 第二层：宽语义召回 ───────────────────────────────────────────
    def _semantic_recall(self, query: str, top_k: int) -> list[dict]:
        """向量语义召回"""
        try:
            return self._indexer.query_skills(query=query, top_k=top_k)
        except Exception as e:
            logger.error(f"Chroma query failed: {e}")
            return []

    # ── 第三层：精排层 ──────────────────────────────────────────────
    def _rerank(self, results: list[dict]) -> list[dict]:
        """阈值过滤 + 得分排序"""
        passed = [r for r in results if r["score"] >= settings.similarity_threshold]
        passed.sort(key=lambda x: x["score"], reverse=True)
        return passed

    # ── 公开检索接口 ───────────────────────────────────────────────
    def match(
        self,
        query: str,
        agent_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """三层检索主入口"""
        # 1. 宽召回
        candidates = self._semantic_recall(query, top_k=min(max(top_k, 1), settings.top_k_recall))
        if not candidates:
            logger.warning(f"No recall for query: {query}")
            return []

        # 2. 元数据过滤
        filtered = self._filter_by_metadata(candidates, agent_type=agent_type)
        if not filtered:
            logger.info("Metadata filter emptied results for query: %s", query)
            return []

        # 3. 精排
        ranked = self._rerank(filtered)
        return ranked[:top_k]
