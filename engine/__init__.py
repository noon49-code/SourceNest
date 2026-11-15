"""SourceNest engine package.

The modules inside this package use bare imports (``from portable import …``,
``import knowledge``, etc.) rather than relative imports.  Inserting the
package directory onto *sys.path* lets those imports resolve without editing
any existing source file.
"""

from __future__ import annotations

import os
import sys

_engine_dir = os.path.dirname(os.path.abspath(__file__))
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from engine.beyin import VERSION, main  # noqa: E402  # re-export

__version__ = VERSION
__all__ = ["main", "VERSION", "__version__"]
