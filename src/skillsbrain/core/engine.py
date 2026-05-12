"""混合检索引擎：向量召回 + 词法精排。"""
import logging
import re
from typing import Optional

from .indexer import SkillIndexer
from skillsbrain.config import settings

logger = logging.getLogger(__name__)

CHINESE_FILLER_PATTERNS = (
    "帮我",
    "请帮我",
    "麻烦",
    "一下",
    "一篇",
    "一个",
    "一份",
    "给我",
    "篇",
    "份",
)

LOW_SIGNAL_CJK_VARIANTS = {
    "生成",
    "查询",
    "查看",
    "修复",
    "排查",
    "处理",
    "分析",
    "整理",
    "输出",
    "更新",
    "昨天",
    "今天",
    "明天",
}

SYNONYM_GROUPS = (
    ("日报", "daily report", "work daily report", "总结今日工作", "写日报", "更新日报"),
    ("前端设计", "frontend design", "web design", "ui design", "页面设计"),
    ("知识库", "knowledge base", "knowledge memory", "记忆库"),
)


class SkillEngine:
    def __init__(self, indexer: SkillIndexer):
        self._indexer = indexer

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = (text or "").strip().lower()
        normalized = normalized.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _expand_query_variants(self, query: str) -> list[str]:
        base = self._normalize_text(query)
        variants = {base, query.strip().lower()}
        for group in SYNONYM_GROUPS:
            normalized_group = {self._normalize_text(item) for item in group}
            if base in normalized_group or any(item and item in base for item in normalized_group):
                variants.update(normalized_group)
        compact = base.replace(" ", "")
        if compact:
            variants.add(compact)
        variants.update(self._extract_intent_phrases(base))
        filtered_variants = []
        for item in variants:
            if not item:
                continue
            compact_item = item.replace(" ", "")
            if compact_item in LOW_SIGNAL_CJK_VARIANTS:
                continue
            filtered_variants.append(item)
        return filtered_variants

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        english_tokens = re.findall(r"[a-z0-9]+", text.lower())
        cjk_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        expanded_cjk_tokens: list[str] = []
        for chunk in cjk_tokens:
            expanded_cjk_tokens.append(chunk)
            length = len(chunk)
            max_size = min(6, length)
            for size in range(2, max_size + 1):
                for start in range(0, length - size + 1):
                    expanded_cjk_tokens.append(chunk[start:start + size])
        return english_tokens + expanded_cjk_tokens

    @staticmethod
    def _contains_variant(field_values: list[str], variant: str) -> bool:
        compact_variant = variant.replace(" ", "")
        for value in field_values:
            normalized = (value or "").strip()
            if not normalized:
                continue
            compact_value = normalized.replace(" ", "")
            if normalized == variant or compact_value == compact_variant:
                return True
            if len(compact_variant) >= 4 and compact_variant in compact_value:
                return True
        return False

    @classmethod
    def _extract_intent_phrases(cls, text: str) -> set[str]:
        phrases: set[str] = set()
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            normalized_chunk = chunk
            for filler in CHINESE_FILLER_PATTERNS:
                normalized_chunk = normalized_chunk.replace(filler, "")
            normalized_chunk = normalized_chunk.strip()
            if len(normalized_chunk) >= 2:
                phrases.add(normalized_chunk)
            length = len(normalized_chunk)
            for size in range(2, min(6, length) + 1):
                for start in range(0, length - size + 1):
                    phrase = normalized_chunk[start:start + size]
                    if len(phrase) >= 2:
                        phrases.add(phrase)
        return phrases

    def _filter_by_metadata(
        self,
        results: list[dict],
        agent_type: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[dict]:
        filtered = []
        for result in results:
            compat = result.get("compatibility") or []
            if isinstance(compat, str):
                compat = [item.strip() for item in compat.split(",") if item.strip()]

            enabled_value = result.get("enabled", True)
            if isinstance(enabled_value, str):
                enabled = enabled_value.lower() == "true"
            else:
                enabled = bool(enabled_value)

            if enabled_only and not enabled:
                continue
            if agent_type and agent_type not in compat:
                continue

            normalized = dict(result)
            normalized["compatibility"] = compat
            normalized["enabled"] = enabled
            if isinstance(normalized.get("tags"), str):
                normalized["tags"] = [item for item in normalized["tags"].split(",") if item]
            if isinstance(normalized.get("aliases"), str):
                normalized["aliases"] = [item for item in normalized["aliases"].split("||") if item]
            if isinstance(normalized.get("keywords"), str):
                normalized["keywords"] = [item for item in normalized["keywords"].split("||") if item]
            filtered.append(normalized)
        return filtered

    def _semantic_recall(self, query: str, top_k: int) -> list[dict]:
        try:
            return self._indexer.query_skills(query=query, top_k=top_k)
        except Exception as exc:
            logger.error("Chroma query failed: %s", exc)
            return []

    def _lexical_score(self, skill: dict, query_variants: list[str], query_tokens: list[str]) -> float:
        skill_id = self._normalize_text(skill.get("skill_id", ""))
        name = self._normalize_text(skill.get("name", ""))
        description = self._normalize_text(skill.get("description", ""))
        search_text = self._normalize_text(skill.get("search_text", ""))
        tags = [self._normalize_text(item) for item in skill.get("tags", [])]
        aliases = [self._normalize_text(item) for item in skill.get("aliases", [])]
        keywords = [self._normalize_text(item) for item in skill.get("keywords", [])]

        searchable = {
            "skill_id": skill_id,
            "name": name,
            "description": description,
            "search_text": search_text,
            "tags": " ".join(tags),
            "aliases": " ".join(aliases),
            "keywords": " ".join(keywords),
        }

        best = 0.0
        for variant in query_variants:
            if not variant:
                continue
            compact_variant = variant.replace(" ", "")
            if variant in {skill_id, name} or compact_variant in {skill_id.replace(" ", ""), name.replace(" ", "")}:
                best = max(best, 1.0)
            if variant and (variant in searchable["name"] or compact_variant in searchable["name"].replace(" ", "")):
                best = max(best, 0.9)
            if variant and (variant in searchable["skill_id"] or compact_variant in searchable["skill_id"].replace(" ", "")):
                best = max(best, 0.88)
            if variant and self._contains_variant(aliases, variant):
                best = max(best, 0.82)
            if variant and self._contains_variant(keywords, variant):
                best = max(best, 0.84)
            if variant and variant in searchable["tags"]:
                best = max(best, 0.8)
            if variant and variant in searchable["description"]:
                best = max(best, 0.72)
            if variant and variant in searchable["search_text"]:
                best = max(best, 0.68)

        if query_tokens:
            haystack_tokens = set(
                self._tokenize(
                    " ".join(
                        [
                            searchable["skill_id"],
                            searchable["name"],
                            searchable["description"],
                            searchable["search_text"],
                            searchable["tags"],
                            searchable["aliases"],
                            searchable["keywords"],
                        ]
                    )
                )
            )
            overlap = len(set(query_tokens) & haystack_tokens) / len(set(query_tokens))
            best = max(best, round(overlap * 0.75, 4))

        return round(min(best, 1.0), 4)

    @staticmethod
    def _blend_scores(vector_score: float, lexical_score: float) -> float:
        vector_score = max(0.0, min(vector_score, 1.0))
        lexical_score = max(0.0, min(lexical_score, 1.0))
        return round(min(1.0, vector_score * 0.55 + lexical_score * 0.65), 4)

    def _min_accept_score(self, query: str) -> float:
        normalized = self._normalize_text(query)
        tokens = self._tokenize(normalized)
        if len(normalized.replace(" ", "")) <= 4 or len(tokens) <= 2:
            return 0.35
        return max(0.5, settings.similarity_threshold)

    def _rerank(self, query: str, results: list[dict]) -> list[dict]:
        query_variants = self._expand_query_variants(query)
        query_tokens = self._tokenize(self._normalize_text(query))
        min_accept = self._min_accept_score(query)

        ranked = []
        for result in results:
            vector_score = float(result.get("score", 0.0))
            lexical_score = self._lexical_score(result, query_variants, query_tokens)
            final_score = self._blend_scores(vector_score, lexical_score)
            if final_score >= min_accept or (lexical_score >= 0.82 and vector_score >= 0.2):
                enriched = dict(result)
                enriched["vector_score"] = round(vector_score, 4)
                enriched["lexical_score"] = lexical_score
                enriched["score"] = final_score
                ranked.append(enriched)

        ranked.sort(
            key=lambda item: (
                item["score"],
                item.get("lexical_score", 0.0),
                item.get("vector_score", 0.0),
            ),
            reverse=True,
        )
        return ranked

    def match(
        self,
        query: str,
        agent_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        recall_k = min(max(top_k, 1), settings.top_k_recall)
        semantic_candidates = self._semantic_recall(query, top_k=recall_k)
        lexical_candidates = self._indexer.iter_skills()

        merged: dict[str, dict] = {}
        for candidate in lexical_candidates:
            skill_id = candidate.get("skill_id")
            if skill_id:
                merged[skill_id] = dict(candidate)

        for candidate in semantic_candidates:
            skill_id = candidate.get("skill_id")
            if not skill_id:
                continue
            existing = merged.get(skill_id, {})
            merged[skill_id] = {**existing, **candidate}

        filtered = self._filter_by_metadata(list(merged.values()), agent_type=agent_type)
        if not filtered:
            logger.info("Metadata filter emptied results for query: %s", query)
            return []

        ranked = self._rerank(query, filtered)
        if not ranked:
            logger.warning("No recall for query after rerank: %s", query)
            return []
        return ranked[:top_k]
