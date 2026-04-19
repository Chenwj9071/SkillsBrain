"""技能中心配置文件"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# HuggingFace 镜像（加速国内下载）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

BASE_DIR = Path(__file__).parent.resolve()
SKILLS_DIR = BASE_DIR / "skills"
INDEX_DIR = BASE_DIR / ".index"
LOG_DIR = BASE_DIR / "logs"


class Settings(BaseSettings):
    # 模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"  # cpu / cuda

    # 检索
    top_k_recall: int = 12   # 宽召回数量
    top_k_final: int = 5      # 最终输出数量
    similarity_threshold: float = 0.65  # 精排阈值（放宽确保召回）

    # 文件监听
    debounce_seconds: float = 1.0

    # 日志
    log_level: str = "INFO"

    class Config:
        env_prefix = "SKILL_CENTER_"


settings = Settings()
