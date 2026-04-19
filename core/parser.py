"""技能元数据解析器"""
import frontmatter
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import yaml


@dataclass
class SkillMeta:
    name: str
    description: str
    compatibility: list[str]
    tags: list[str]
    version: str
    author: str
    enabled: bool
    created_at: str
    file_path: str  # 绝对路径

    def to_dict(self):
        return asdict(self)


class SkillParser:
    @staticmethod
    def parse(file_path: Path) -> Optional[SkillMeta]:
        try:
            post = frontmatter.loads(file_path.read_text(encoding="utf-8"))
            km = post.metadata or {}

            # 智能推断 name（文件名兜底）
            name = str(km.get("name") or file_path.stem).strip()
            if not name:
                return None

            return SkillMeta(
                name=name,
                description=str(km.get("description", "")),
                compatibility=km.get("compatibility", ["claude_code", "codex"]),
                tags=km.get("tags", []),
                version=str(km.get("version", "1.0.0")),
                author=str(km.get("author", "local-agent")),
                enabled=bool(km.get("enabled", True)),
                created_at=str(km.get("created_at", "")),
                file_path=str(file_path.resolve()),
            )
        except Exception:
            return None
