from pathlib import Path
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from skillsbrain.core.engine import SkillEngine
from skillsbrain.core.indexer import SkillIndexer
from skillsbrain.core.parser import SkillParser


class DummyModel:
    def encode(self, texts, normalize_embeddings=True):
        if isinstance(texts, str):
            texts = [texts]
        return [[float(i + 1)] * 3 for i, _ in enumerate(texts)]


def main():
    base = Path(tempfile.mkdtemp(prefix="skillsbrain_test_"))
    skills_dir = base / "skills"
    index_dir = base / "index"
    (skills_dir / "alpha").mkdir(parents=True)
    (skills_dir / "beta").mkdir(parents=True)

    (skills_dir / "alpha" / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: alpha-skill
            description: alpha task
            compatibility: claude_code
            aliases: [alpha helper]
            keywords: [alpha, helper]
            tags: alpha
            enabled: true
            ---
            body
            """
        ),
        encoding="utf-8",
    )

    (skills_dir / "beta" / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: beta-skill
            description: beta task
            compatibility: [codex]
            tags: [beta, sheet]
            enabled: "false"
            ---
            body
            """
        ),
        encoding="utf-8",
    )

    parser = SkillParser(skills_dir)
    alpha = parser.parse(skills_dir / "alpha" / "SKILL.md")
    beta = parser.parse(skills_dir / "beta" / "SKILL.md")
    assert alpha is not None and alpha.skill_id == "alpha"
    assert alpha.compatibility == ["claude_code"]
    assert alpha.tags == ["alpha"]
    assert isinstance(alpha.search_text, str)
    assert isinstance(alpha.aliases, list)
    assert "alpha helper" in alpha.aliases
    assert alpha.keywords == ["alpha", "helper"]
    assert beta is not None and beta.skill_id == "beta"
    assert beta.enabled is False
    assert beta.tags == ["beta", "sheet"]

    indexer = SkillIndexer(skills_dir=skills_dir, index_dir=index_dir)
    indexer._model = DummyModel()
    count = indexer.full_sync()
    assert count == 2
    stored = indexer._collection.get(include=["metadatas"])
    assert set(stored["ids"]) == {"local:alpha", "local:beta"}

    (skills_dir / "beta" / "SKILL.md").unlink()
    indexer.delete_skill(skills_dir / "beta" / "SKILL.md")
    stored_after_delete = indexer._collection.get(include=["metadatas"])
    assert set(stored_after_delete["ids"]) == {"local:alpha"}

    (skills_dir / "gamma").mkdir(parents=True)
    (skills_dir / "gamma" / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            name: gamma-skill
            description: gamma task
            compatibility: [claude_code]
            tags: gamma
            enabled: true
            ---
            body
            """
        ),
        encoding="utf-8",
    )
    count2 = indexer.full_sync()
    assert count2 == 2
    stored_after_sync = indexer._collection.get(include=["metadatas"])
    assert set(stored_after_sync["ids"]) == {"local:alpha", "local:gamma"}

    engine = SkillEngine(indexer)
    engine._semantic_recall = lambda query, top_k: [
        {"skill_id": "local:only-codex", "name": "only-codex", "compatibility": "codex", "enabled": "True", "score": 0.9},
    ]
    assert engine.match("x", agent_type="claude_code", top_k=5) == []

    bad_file = skills_dir / "bad" / "SKILL.md"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text(
        textwrap.dedent(
            """\
            ---
            name: bad-skill
            enabled: maybe
            ---
            body
            """
        ),
        encoding="utf-8",
    )
    assert parser.parse(bad_file) is None

    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
