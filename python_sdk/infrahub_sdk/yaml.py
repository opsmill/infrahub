from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class SchemaFile(BaseModel):
    identifier: Optional[str] = None
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
