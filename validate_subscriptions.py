from pathlib import Path
import sys
import tempfile
import textwrap

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from skillsbrain.core.indexer import SkillIndexer
from skillsbrain.core.parser import SkillParser


class DummyModel:
    def encode(self, texts, normalize_embeddings=True):
        if isinstance(texts, str):
            texts = [texts]
        return [[float(i + 1)] * 3 for i, _ in enumerate(texts)]


def write_skill(root: Path, name: str, enabled: str = "true"):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        textwrap.dedent(
            f"""\
            ---
            name: {name}
            description: {name} desc
            compatibility: [claude_code]
            tags: [{name}]
            enabled: {enabled}
            ---
            body
            """
        ),
        encoding="utf-8",
    )


def main():
    base = Path(tempfile.mkdtemp(prefix="skillsbrain_sub_test_"))
    local = base / "local"
    sub = base / "sub"
    index = base / "index"
    local.mkdir()
    sub.mkdir()

    write_skill(local, "alpha")
    write_skill(sub, "beta")

    indexer = SkillIndexer(skills_dir=local, index_dir=index)
    indexer._model = DummyModel()

    total = indexer.full_sync()
    assert total == 1
    skills, total_list = indexer.list_skills(limit=10)
    assert total_list == 1
    assert skills[0]["skill_id"] == "local:alpha"

    sub_result = indexer.subscribe_source(sub, name="shared")
    assert sub_result["name"] == "shared"
    assert sub_result["indexed"] == 1

    skills, total_list = indexer.list_skills(limit=10)
    ids = {item["skill_id"] for item in skills}
    assert "shared:beta" in ids
    assert "local:alpha" in ids

    subs = indexer.list_subscriptions()
    assert any(item["name"] == "shared" for item in subs)

    unsub_result = indexer.unsubscribe_source("shared")
    assert unsub_result["removed"] == 1

    skills, total_list = indexer.list_skills(limit=10)
    ids = {item["skill_id"] for item in skills}
    assert "shared:beta" not in ids
    assert "local:alpha" in ids

    print("SUBSCRIPTION_VALIDATION_OK")


if __name__ == "__main__":
    main()
