"""技能元数据解析器"""
import logging
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
    file_path: str  # 绝对路径
    relative_path: str

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

            return SkillMeta(
                skill_id=skill_id,
                name=name,
                description=str(km.get("description", "")).strip(),
                compatibility=self._normalize_list(km.get("compatibility"), ["claude_code", "codex"]),
                tags=self._normalize_list(km.get("tags"), []),
                version=str(km.get("version", "1.0.0")).strip(),
                author=str(km.get("author", "local-agent")).strip(),
                enabled=self._normalize_bool(km.get("enabled", True)),
                created_at=str(km.get("created_at", "")).strip(),
                file_path=str(resolved_path),
                relative_path=relative_path,
            )
        except Exception:
            logger.exception("Failed to parse skill file: %s", file_path)
            return None
