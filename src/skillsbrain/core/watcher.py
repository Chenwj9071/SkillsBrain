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

    def __init__(self, indexer, root: Path, source_name: str, debounce: float = 1.0):
        self.indexer = indexer
        self.root = Path(root).resolve()
        self.source_name = source_name
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
        logger.info("Skill created: %s", event.src_path)
        self._debounced(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith("SKILL.md"):
            return
        logger.info("Skill modified: %s", event.src_path)
        self._debounced(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory or not event.src_path.endswith("SKILL.md"):
            return
        logger.info("Skill deleted: %s", event.src_path)
        self._debounced(event.src_path, "deleted")


def start_watcher(indexer, root: Path | None = None, source_name: str = "local"):
    watch_root = Path(root or indexer.skills_dir).resolve()
    handler = SkillChangeHandler(indexer, root=watch_root, source_name=source_name, debounce=settings.debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(watch_root), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info("File watcher started on: %s (%s)", watch_root, source_name)
    return observer


def stop_watcher(observer: Observer | None):
    if observer is None:
        return
    observer.stop()
    observer.join(timeout=5)
    logger.info("File watcher stopped.")


def stop_observer(observer: Observer | None):
    stop_watcher(observer)
