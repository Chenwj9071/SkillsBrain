"""SkillsBrain configuration"""
import os
from pathlib import Path
from platform import system

from pydantic_settings import BaseSettings

# HuggingFace 镜像（加速国内下载）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _default_base_dir() -> Path:
    if system().lower() == "windows":
        home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    else:
        home = Path.home()
    return home / ".skillsbrain"


class Settings(BaseSettings):
    # 技能目录（可由环境变量覆盖）
    skills_dir: str = str(_default_base_dir() / "skills")

    # 索引目录
    index_dir: str = str(_default_base_dir() / ".index")

    # 日志目录
    log_dir: str = str(_default_base_dir() / "logs")

    # 模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"  # cpu / cuda

    # 检索
    top_k_recall: int = 12   # 宽召回数量
    top_k_final: int = 5     # 最终输出数量
    similarity_threshold: float = 0.65  # 精排阈值

    # Web / CORS
    cors_origins: str = "http://127.0.0.1,http://localhost"

    # 文件监听
    debounce_seconds: float = 1.0

    # 订阅源配置
    subscriptions_file: str = str(Path.cwd() / ".index" / "subscriptions.json")

    class Config:
        env_prefix = "SKILLSBRAIN_"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
