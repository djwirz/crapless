"""The real server with scripted dice, for the browser test and the README GIF only.

It listens on localhost alone, and nothing that is deployed imports it.
"""

from itertools import cycle
from pathlib import Path

import uvicorn

from crapless.server.app import create_app

PORT = 8766
PAGE = Path(__file__).parent.parent / "web" / "dist"
# A turn each. First: 6 is the point, a Come bet travels to 9, Place 8 hits, then seven out.
# Second: 4 is the point, then seven out.
ROLLS = [(3, 3), (5, 4), (4, 4), (3, 4), (2, 2), (4, 3)]

if __name__ == "__main__":
    script = cycle(ROLLS)
    uvicorn.run(create_app(dice=lambda: next(script), static=PAGE), host="127.0.0.1", port=PORT)
