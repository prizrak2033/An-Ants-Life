from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class Intent:
    target: Optional[Tuple[float, float]] = None
    deposit_channel: Optional[str] = None  # "food" | "home" | None
