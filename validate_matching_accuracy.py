from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from skillsbrain.core.engine import SkillEngine
from skillsbrain.core.indexer import SkillIndexer


def main():
    indexer = SkillIndexer()
    engine = SkillEngine(indexer)

    cases = [
        ("kg-daily-report", "local:kg-daily-report"),
        ("日报", "ai-skills:work-daily-report"),
        ("帮我写一篇日报", "ai-skills:work-daily-report"),
        ("帮我总结今天工作并写日报", "ai-skills:work-daily-report"),
        ("daily report", "ai-skills:work-daily-report"),
        ("前端设计", "local:frontend-design"),
        ("frontend design", "local:frontend-design"),
    ]

    for query, expected in cases:
        matches = engine.match(query, agent_type="codex", top_k=5)
        if not matches:
            raise AssertionError(f"Query '{query}' returned no matches")
        top = matches[0]
        print(f"{query} -> {top['skill_id']} ({top['score']:.4f})")
        if top["skill_id"] != expected:
            raise AssertionError(f"Query '{query}' expected top result '{expected}', got '{top['skill_id']}'")

    detailed = engine.match(
        "Use when user asks to summarize daily work, write daily report, or update daily report in Chinese",
        agent_type="codex",
        top_k=5,
    )
    if len(detailed) < 2:
        raise AssertionError("Expected at least 2 results for daily report long query")
    if detailed[0]["skill_id"] != "ai-skills:work-daily-report":
        raise AssertionError("Long daily report query did not rank work-daily-report first")
    if detailed[0]["score"] - detailed[1]["score"] < 0.15:
        raise AssertionError("Long daily report query still lacks score separation")
    print(
        "long-query separation -> "
        f"{detailed[0]['skill_id']} {detailed[0]['score']:.4f} vs {detailed[1]['skill_id']} {detailed[1]['score']:.4f}"
    )

    print("MATCHING_VALIDATION_OK")


if __name__ == "__main__":
    main()
