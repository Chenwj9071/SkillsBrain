"""技能文件监听器（增量同步）"""
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import logging

from config import settings
from core.indexer import SkillIndexer

logger = logging.getLogger(__name__)


class SkillChangeHandler(FileSystemEventHandler):
    """监听 SKILL.md 变化，防抖 1s 后更新索引"""

    def __init__(self, indexer: SkillIndexer, debounce: float = 1.0):
        self.indexer = indexer
        self.debounce = debounce
        self._pending: dict[str, float] = {}  # path → trigger time
        self._lock = threading.Lock()

    def _debounced(self, path: str, op: str):
        with self._lock:
            now = time.time()
            self._pending[path] = now

        def _flush():
            time.sleep(self.debounce)
            with self._lock:
                trigger_time = self._pending.pop(path, None)
            if trigger_time and trigger_time == now:
                p = Path(path)
                if op == "deleted":
                    self.indexer.delete_skill(p)
                else:
                    self.indexer.update_skill(p)

        threading.Thread(target=_flush, daemon=True).start()

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith("SKILL.md"):
            return
        logger.info(f"Skill created: {event.src_path}")
        self._debounced(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith("SKILL.md"):
            return
        logger.info(f"Skill modified: {event.src_path}")
        self._debounced(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith("SKILL.md"):
            return
        logger.info(f"Skill deleted: {event.src_path}")
        self._debounced(event.src_path, "deleted")


def start_watcher(indexer: SkillIndexer):
    from config import SKILLS_DIR
    handler = SkillChangeHandler(indexer, debounce=settings.debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(SKILLS_DIR), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info(f"File watcher started on: {SKILLS_DIR}")
    return observer
