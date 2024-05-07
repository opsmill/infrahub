from pathlib import Path
from typing import Optional

import yaml

try:
    from pydantic import v1 as pydantic  # type: ignore[attr-defined]
except ImportError:
    import pydantic  # type: ignore[no-redef]


class SchemaFile(pydantic.BaseModel):
    identifier: Optional[str]
    location: Path
    content: Optional[dict] = None
    valid: bool = True
    error_message: Optional[str] = None

    def load_content(self) -> None:
        try:
            self.content = yaml.safe_load(self.location.read_text())
        except yaml.YAMLError:
            self.error_message = "Invalid YAML/JSON file"
            self.valid = False
            return

        if not self.content:
            self.error_message = "Empty YAML/JSON file"
            self.valid = False
