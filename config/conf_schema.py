"""OmegaConf 结构化配置 Schema。"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    model_name: str = "LongCat-2.0"
    base_url: str = "https://api.longcat.chat/openai/v1"
    api_key: str = ""
    timeout: float = 60.0
    max_retries: int = 2


@dataclass
class KBConfig:
    chunk_size: int = 512
    chunk_overlap: int = 128
    top_k: int = 5
    hybrid_alpha: float = 0.5  # 向量检索权重，1-alpha = BM25 权重


@dataclass
class WindowConfig:
    width: int = 980
    height: int = 660
    min_width: int = 820
    min_height: int = 560


@dataclass
class ReminderConfig:
    remind_sedentary: bool = True
    remind_drink_water: bool = True
    sedentary_interval_min: int = 60
    drink_water_interval_min: int = 45


@dataclass
class AppConfig:
    run_mode: str = "online"
    auto_start: bool = False
    llm: LLMConfig = field(default_factory=LLMConfig)
    kb: KBConfig = field(default_factory=KBConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    reminder: ReminderConfig = field(default_factory=ReminderConfig)
