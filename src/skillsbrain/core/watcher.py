"""技能文件监听器（增量同步）"""
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import logging

from skillsbrain.config import settings

logger = logging.getLogger(__name__)


class SkillChangeHandler(FileSystemEventHandler):
    """监听 SKILL.md 变化，防抖 1s 后更新索引"""

    def __init__(self, indexer, debounce: float = 1.0):
        self.indexer = indexer
        self.debounce = debounce
        self._pending: dict[str, float] = {}
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


def start_watcher(indexer):
    handler = SkillChangeHandler(indexer, debounce=settings.debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(indexer.skills_dir), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info(f"File watcher started on: {indexer.skills_dir}")
    return observer


def stop_watcher(observer: Observer | None):
    if observer is None:
        return
    observer.stop()
    observer.join(timeout=5)
    logger.info("File watcher stopped.")
