"""订阅源管理"""
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from skillsbrain.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    name: str
    root: str
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class SubscriptionStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or settings.subscriptions_file).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Subscription]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return [Subscription(**item) for item in payload]
        except Exception:
            logger.exception("Failed to load subscriptions: %s", self.path)
            return []

    def save(self, subscriptions: list[Subscription]) -> None:
        payload = [item.to_dict() for item in subscriptions]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, subscription: Subscription) -> None:
        subscriptions = self.load()
        subscriptions = [item for item in subscriptions if item.name != subscription.name and Path(item.root).resolve() != Path(subscription.root).resolve()]
        subscriptions.append(subscription)
        self.save(subscriptions)

    def remove(self, name_or_root: str) -> bool:
        subscriptions = self.load()
        target = Path(name_or_root).resolve() if Path(name_or_root).exists() else None
        kept = []
        removed = False
        for item in subscriptions:
            if item.name == name_or_root:
                removed = True
                continue
            if target is not None and Path(item.root).resolve() == target:
                removed = True
                continue
            kept.append(item)
        if removed:
            self.save(kept)
        return removed

    def get(self, name: str) -> Optional[Subscription]:
        for item in self.load():
            if item.name == name:
                return item
        return None
