"""The four strategies, as modules, in evaluation order.

WHY MODULES AND NOT CLASSES OR A PROTOCOL. Each strategy is `NAME`,
`CONDITIONS` and one `evaluate` function with no state -- a class with one
method and no state is a function, and a Protocol with four implementors that
never vary the signature is a type annotation wearing an abstraction's clothes.
A module already has a name, module-level constants, and one public function.

The order is S1..S4 and it is the order the engine evaluates them in, which
matters only when two strategies suggest on the same bar: the engine takes at
most one position, so the tie has to break somewhere, and it breaks here rather
than on a score comparison. `engine.py` documents why that is deliberate.
"""

from __future__ import annotations

from typing import Any

from track_c.strategies import s1, s2, s3, s4

ALL: tuple[Any, ...] = (s1, s2, s3, s4)

CONDITIONS: dict[str, tuple[str, ...]] = {m.NAME: m.CONDITIONS for m in ALL}
