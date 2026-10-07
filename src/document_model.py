import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

@dataclass
class DocumentBlock:
    block_id: int
    block_type: str  # paragraph, table, table_row, table_cell, equation, image, header, footer, page_break, section_break, ocr_text, etc.
    text: str = ""
    page: Optional[int] = None
    order: int = 0
    source: str = "docx"  # or pdf
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['DocumentBlock'] = field(default_factory=list) # For nested blocks like tables -> rows -> cells

    def to_dict(self):
        d = asdict(self)
        d['children'] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict):
        children = [cls.from_dict(c) for c in d.pop('children', [])]
        return cls(**d, children=children)
