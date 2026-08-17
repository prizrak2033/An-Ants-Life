"""
Chronicle: the recent story, as prose.

Reads the significant events only. Routine foraging and combat churn
account for the large majority of the log, so a plain tail of the event
list showed nothing but noise.
"""
from __future__ import annotations

from colony.narrator import chronicle_lines


def format_chronicle(state) -> str:
    lines = chronicle_lines(state.history, state.cfg.CHRONICLE_N_EVENTS)
    if not lines:
        return ""
    out = []
    for l in lines[-3:]:
        suffix = f" (x{l['repeat']})" if l["repeat"] > 1 else ""
        out.append(f"    · {l['text']}{suffix}")
    return "\n".join(out)
