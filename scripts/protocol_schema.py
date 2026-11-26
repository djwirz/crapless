"""Write the protocol's JSON Schema, which the TypeScript types are generated from."""

import json
from pathlib import Path

from crapless.server.messages import Protocol

SCHEMA = Path(__file__).parent.parent / "web" / "protocol.schema.json"


def schema_text() -> str:
    schema = Protocol.model_json_schema()
    _drop_property_titles(schema)
    return json.dumps(schema, indent=2) + "\n"


def _drop_property_titles(node: object) -> None:
    """Without this, every field gets a type alias of its own in TypeScript."""
    if isinstance(node, dict):
        for child in node.get("properties", {}).values():
            child.pop("title", None)
        for child in node.values():
            _drop_property_titles(child)
    elif isinstance(node, list):
        for child in node:
            _drop_property_titles(child)


if __name__ == "__main__":
    SCHEMA.write_text(schema_text())
