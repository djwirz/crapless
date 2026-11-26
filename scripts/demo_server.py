"""The real server with scripted dice, for the browser test and the README GIF only.

It listens on localhost alone, and nothing that is deployed imports it.
"""

from itertools import cycle
from pathlib import Path

import uvicorn

from crapless.server.app import create_app

PORT = 8766
PAGE = Path(__file__).parent.parent / "web" / "dist"
# One hand: 6 is the point, a Come bet travels to 9, Place 8 hits, 9 pays, 6 makes the point.
ROLLS = [(3, 3), (5, 4), (4, 4), (6, 3), (4, 2)]

if __name__ == "__main__":
    script = cycle(ROLLS)
    uvicorn.run(create_app(dice=lambda: next(script), static=PAGE), host="127.0.0.1", port=PORT)
