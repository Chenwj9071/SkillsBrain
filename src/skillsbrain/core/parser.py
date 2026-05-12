"""技能元数据解析器。"""
import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import frontmatter

logger = logging.getLogger(__name__)


@dataclass
class SkillMeta:
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
    search_text: str
    aliases: list[str]
    keywords: list[str]

    def to_dict(self):
        return asdict(self)


class SkillParser:
    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir).resolve()

    def _build_skill_id(self, file_path: Path) -> str:
        relative_path = file_path.resolve().relative_to(self.skills_dir)
        if relative_path.name == "SKILL.md" and relative_path.parent != Path("."):
            return relative_path.parent.as_posix()
        return relative_path.as_posix()

    @staticmethod
    def _normalize_list(value, default: list[str]) -> list[str]:
        if value is None:
            return list(default)
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, (list, tuple, set)):
            normalized = []
            for item in value:
                text = str(item).strip()
                if text:
                    normalized.append(text)
            return normalized
        text = str(value).strip()
        return [text] if text else []

    @staticmethod
    def _normalize_bool(value, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            raise ValueError(f"Invalid boolean value: {value}")
        if isinstance(value, (int, float)):
            return bool(value)
        raise ValueError(f"Invalid boolean type: {type(value).__name__}")

    @staticmethod
    def _clean_markdown_line(line: str) -> str:
        text = line.strip()
        if not text:
            return ""
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text)
        text = re.sub(r"^\s*[-*+]\s+", "", text)
        text = re.sub(r"^\s*\d+\.\s+", "", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"[>*_~]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip(" -|:")

    @staticmethod
    def _looks_like_low_signal(text: str) -> bool:
        lowered = text.lower()
        if len(text) < 4:
            return True
        if text.startswith(("C:\\", "/", ".\\", "../")):
            return True
        if "http://" in lowered or "https://" in lowered:
            return True
        if text.count("\\") >= 2 or text.count("/") >= 4:
            return True
        if re.fullmatch(r"[-=:`'._/\\\s]+", text):
            return True
        return False

    def _extract_search_summary(self, content: str) -> str:
        lines = content.splitlines()
        in_code_block = False
        priority: list[str] = []
        normal: list[str] = []
        seen: set[str] = set()

        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            cleaned = self._clean_markdown_line(raw_line)
            if not cleaned or self._looks_like_low_signal(cleaned):
                continue

            lowered = cleaned.lower()
            is_priority = any(
                key in lowered
                for key in (
                    "use when",
                    "when the user asks",
                    "overview",
                    "summary",
                    "适用",
                    "场景",
                    "用途",
                    "用于",
                )
            )
            bucket = priority if is_priority else normal
            if cleaned not in seen:
                bucket.append(cleaned)
                seen.add(cleaned)

        selected: list[str] = []
        for item in priority + normal:
            selected.append(item)
            if len(" ".join(selected)) >= 700 or len(selected) >= 10:
                break
        return " ".join(selected).strip()

    @staticmethod
    def _is_high_signal_alias(text: str) -> bool:
        candidate = re.sub(r"\s+", " ", text).strip()
        if len(candidate) < 2 or len(candidate) > 48:
            return False
        if any(mark in candidate for mark in (":", "：", "。", "；", ";", "!", "！", "?", "？")):
            return False
        if candidate.count(",") + candidate.count("，") > 1:
            return False
        if len(candidate.split()) > 6:
            return False
        cjk_chunks = re.findall(r"[\u4e00-\u9fff]+", candidate)
        if cjk_chunks and max(len(chunk) for chunk in cjk_chunks) > 12:
            return False
        return True

    @classmethod
    def _extract_aliases(cls, name: str, description: str) -> list[str]:
        raw_values = [name, description]
        aliases: list[str] = []
        seen: set[str] = set()

        def add_alias(value: str) -> None:
            text = value.strip().strip("()[]{}\"'“”‘’")
            normalized = re.sub(r"\s+", " ", text)
            if not cls._is_high_signal_alias(normalized):
                return
            key = normalized.casefold()
            if key in seen:
                return
            seen.add(key)
            aliases.append(normalized)

        for value in raw_values:
            add_alias(value)
            for part in re.split(r"[()（）;,，。/]+", value):
                add_alias(part)
            for match in re.findall(r"[A-Za-z][A-Za-z0-9 _-]{2,60}", value):
                add_alias(match)
            for match in re.findall(r"[\u4e00-\u9fff]{2,20}", value):
                add_alias(match)

        return aliases[:20]

    @classmethod
    def _extract_keywords(cls, name: str, description: str, summary: str) -> list[str]:
        source = " ".join(part for part in (name, description, summary) if part)
        keywords: list[str] = []
        seen: set[str] = set()

        def add_keyword(value: str) -> None:
            text = re.sub(r"\s+", " ", value).strip("()[]{}\"'“”‘’ ,，。:：;；")
            if len(text) < 2 or len(text) > 48:
                return
            lowered = text.lower()
            if lowered.startswith(("overview", "summary hint", "default flow", "common commands")):
                return
            key = text.casefold()
            if key in seen:
                return
            seen.add(key)
            keywords.append(text)

        for match in re.findall(r"[A-Za-z][A-Za-z0-9 _-]{2,40}", source):
            if len(match.split()) <= 6:
                add_keyword(match)
        for match in re.findall(r"[\u4e00-\u9fff]{2,16}", source):
            add_keyword(match)
        for part in re.split(r"[()（）,，/]+", description):
            add_keyword(part)

        return keywords[:30]

    @staticmethod
    def _merge_unique_lists(*groups: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                text = str(item).strip()
                if len(text) < 2:
                    continue
                key = re.sub(r"\s+", " ", text).casefold()
                if key in seen:
                    continue
                seen.add(key)
                merged.append(re.sub(r"\s+", " ", text))
        return merged

    def parse(self, file_path: Path) -> Optional[SkillMeta]:
        try:
            resolved_path = file_path.resolve()
            post = frontmatter.loads(resolved_path.read_text(encoding="utf-8"))
            km = post.metadata or {}

            skill_id = self._build_skill_id(resolved_path)
            relative_path = resolved_path.relative_to(self.skills_dir).as_posix()
            name = str(km.get("name") or skill_id).strip()
            if not name:
                raise ValueError("Skill name is empty")

            description = str(km.get("description", "")).strip()
            summary = self._extract_search_summary(post.content or "")
            auto_aliases = self._extract_aliases(name, description)
            auto_keywords = self._extract_keywords(name, description, summary)
            manual_aliases = self._normalize_list(km.get("aliases"), [])
            manual_keywords = self._normalize_list(km.get("keywords"), [])
            aliases = self._merge_unique_lists(manual_aliases, auto_aliases)
            keywords = self._merge_unique_lists(manual_keywords, auto_keywords)

            return SkillMeta(
                skill_id=skill_id,
                name=name,
                description=description,
                compatibility=self._normalize_list(km.get("compatibility"), ["claude_code", "codex"]),
                tags=self._normalize_list(km.get("tags"), []),
                version=str(km.get("version", "1.0.0")).strip(),
                author=str(km.get("author", "local-agent")).strip(),
                enabled=self._normalize_bool(km.get("enabled", True)),
                created_at=str(km.get("created_at", "")).strip(),
                file_path=str(resolved_path),
                relative_path=relative_path,
                search_text=summary,
                aliases=aliases,
                keywords=keywords,
            )
        except Exception:
            logger.exception("Failed to parse skill file: %s", file_path)
            return None
