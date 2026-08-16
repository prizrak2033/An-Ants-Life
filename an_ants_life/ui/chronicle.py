"""
Chronicle: renders the most recent notable history events as a short
console readout, giving color to what's driving the current chapter.
"""
from __future__ import annotations


def format_chronicle(state) -> str:
    cfg = state.cfg
    events = state.history.recent(cfg.CHRONICLE_N_EVENTS)
    if not events:
        return ""
    lines = "; ".join(e.headline() for e in events[-3:])
    return f"    chronicle: {lines}"
