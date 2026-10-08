import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class InlineContent:
    """Loss-minimizing inline item shared by DOCX and PDF extractors.

    `kind` is text, math, image, line_break, or a structural math operand.
    `value` is the legacy-readable text while children retain the source tree.
    """
    kind: str
    value: str = ""
    vertical_align: Optional[str] = None
    formatting: Dict[str, Any] = field(default_factory=dict)
    children: List['InlineContent'] = field(default_factory=list)
    source: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> 'InlineContent':
        data = dict(value)
        children = [cls.from_dict(child) if isinstance(child, dict) else child
                    for child in data.pop("children", [])]
        return cls(**data, children=children)


@dataclass
class DocumentBlock:
    block_id: Any = 0  # int or str (e.g. 1, "1.opt_a")
    block_type: str = "paragraph"  # paragraph, table, table_row, table_cell, equation, image, header, footer, page_break, section_break, ocr_text, etc.
    text: str = ""
    page: Optional[int] = None
    order: int = 0
    source: str = "docx"  # or pdf
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['DocumentBlock'] = field(default_factory=list)  # For nested blocks like tables -> rows -> cells
    runs: List[Dict[str, Any]] = field(default_factory=list)  # Inline runs: text, math, sup, sub, image, break
    inline_content: List[InlineContent] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d['children'] = [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.children]
        d['inline_content'] = [c.to_dict() if hasattr(c, 'to_dict') else c
                               for c in self.inline_content]
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d_copy = dict(d)
        children = [cls.from_dict(c) if isinstance(c, dict) else c for c in d_copy.pop('children', [])]
        runs = d_copy.pop('runs', [])
        inline_content = [InlineContent.from_dict(c) if isinstance(c, dict) else c
                          for c in d_copy.pop('inline_content', [])]
        return cls(**d_copy, children=children, runs=runs,
                   inline_content=inline_content)
