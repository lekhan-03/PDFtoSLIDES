from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from pathlib import Path
from src.document_model import DocumentBlock

def extract_docx_blocks(docx_path: str) -> list[DocumentBlock]:
    doc = Document(docx_path)
    M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    
    def extract_node(node):
            text = []
            tag = node.tag.split('}')[-1]

            if tag == 't':
                text.append(node.text or '')
            elif tag == 'tab':
                text.append('\t')
            elif tag == 'f':
                num = node.find(f'.//{M_NS}num')
                den = node.find(f'.//{M_NS}den')
                n_txt = extract_node(num).strip() if num is not None else ''
                d_txt = extract_node(den).strip() if den is not None else ''
                text.append(f'({n_txt})/({d_txt})')
            elif tag == 'sSup':
                e = node.find(f'.//{M_NS}e')
                sup = node.find(f'.//{M_NS}sup')
                e_txt = extract_node(e).strip() if e is not None else ''
                sup_txt = extract_node(sup).strip() if sup is not None else ''
                text.append(f'{e_txt}^{{{sup_txt}}}')
            elif tag == 'sSub':
                e = node.find(f'.//{M_NS}e')
                sub = node.find(f'.//{M_NS}sub')
                e_txt = extract_node(e).strip() if e is not None else ''
                sub_txt = extract_node(sub).strip() if sub is not None else ''
                text.append(f'{e_txt}_{{{sub_txt}}}')
            elif tag == 'sSubSup':
                e = node.find(f'.//{M_NS}e')
                sub = node.find(f'.//{M_NS}sub')
                sup = node.find(f'.//{M_NS}sup')
                e_txt = extract_node(e).strip() if e is not None else ''
                sub_txt = extract_node(sub).strip() if sub is not None else ''
                sup_txt = extract_node(sup).strip() if sup is not None else ''
                text.append(f'{e_txt}_{{{sub_txt}}}^{{{sup_txt}}}')
            elif tag == 'rad':
                deg = node.find(f'.//{M_NS}deg')
                e = node.find(f'.//{M_NS}e')
                deg_txt = extract_node(deg).strip() if deg is not None else ''
                e_txt = extract_node(e).strip() if e is not None else ''
                if deg_txt:
                    text.append(f'root({deg_txt}, {e_txt})')
                else:
                    text.append(f'sqrt({e_txt})')
            elif tag == 'nary':
                pr = node.find(f'.//{M_NS}naryPr')
                chr_val = '∫' # default n-ary char is integral
                if pr is not None:
                    chr_elem = pr.find(f'.//{M_NS}chr')
                    if chr_elem is not None:
                        chr_val = chr_elem.attrib.get(f'{M_NS}val', '∫')

                sub = node.find(f'.//{M_NS}sub')
                sup = node.find(f'.//{M_NS}sup')
                e = node.find(f'.//{M_NS}e')

                sub_txt = extract_node(sub).strip() if sub is not None else ''
                sup_txt = extract_node(sup).strip() if sup is not None else ''
                e_txt = extract_node(e).strip() if e is not None else ''

                res = chr_val
                if sub_txt or sup_txt:
                    res += f'_{{{sub_txt}}}^{{{sup_txt}}}'
                if e_txt:
                    res += f' {e_txt}'
                text.append(res)
            elif tag == 'd':
                pr = node.find(f'.//{M_NS}dPr')
                beg = '('
                end = ')'
                if pr is not None:
                    b = pr.find(f'.//{M_NS}begChr')
                    if b is not None: beg = b.attrib.get(f'{M_NS}val', '(')
                    e = pr.find(f'.//{M_NS}endChr')
                    if e is not None: end = e.attrib.get(f'{M_NS}val', ')')

                e_node = node.find(f'.//{M_NS}e')
                e_txt = extract_node(e_node) if e_node is not None else ''
                text.append(f'{beg}{e_txt}{end}')
            elif tag == 'br':
                text.append('\n')
            elif tag == 'acc':
                pr = node.find(f'.//{M_NS}accPr')
                chr_val = '̂'
                if pr is not None:
                    chr_elem = pr.find(f'.//{M_NS}chr')
                    if chr_elem is not None:
                        chr_val = chr_elem.attrib.get(f'{M_NS}val', '̂')

                e_node = node.find(f'.//{M_NS}e')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''

                if e_txt:
                    acc_map = {
                        '⃗': r'\vec',
                        '̂': r'\hat',
                        '̃': r'\tilde',
                        '̄': r'\bar',
                        '̇': r'\dot',
                        '̈': r'\ddot',
                        '→': r'\vec',
                    }
                    cmd = acc_map.get(chr_val, r'\hat')
                    text.append(f'{cmd}{{{e_txt}}}')
            elif tag == 'bar':
                pr = node.find(f'.//{M_NS}barPr')
                pos = 'top'
                if pr is not None:
                    pos_elem = pr.find(f'.//{M_NS}pos')
                    if pos_elem is not None:
                        pos = pos_elem.attrib.get(f'{M_NS}val', 'top')

                e_node = node.find(f'.//{M_NS}e')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''

                if e_txt:
                    if pos == 'top':
                        text.append(f'\\overline{{{e_txt}}}')
                    else:
                        text.append(f'\\underline{{{e_txt}}}')
            elif tag == 'func':
                fname = node.find(f'.//{M_NS}fName')
                e_node = node.find(f'.//{M_NS}e')
                fname_txt = extract_node(fname).strip() if fname is not None else ''
                e_txt = extract_node(e_node).strip() if e_node is not None else ''
                # Output func like \sin{x} if standard, or just plain if unknown
                if fname_txt in ('sin', 'cos', 'tan', 'sec', 'cosec', 'cot', 'log', 'ln', 'exp'):
                    text.append(f'\\{fname_txt}{{{e_txt}}}')
                else:
                    text.append(f'{fname_txt}{{{e_txt}}}')
            elif tag == 'limLow':
                e_node = node.find(f'.//{M_NS}e')
                lim = node.find(f'.//{M_NS}lim')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''
                lim_txt = extract_node(lim).strip() if lim is not None else ''
                text.append(f'{e_txt}_{{{lim_txt}}}')
            elif tag == 'limUpp':
                e_node = node.find(f'.//{M_NS}e')
                lim = node.find(f'.//{M_NS}lim')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''
                lim_txt = extract_node(lim).strip() if lim is not None else ''
                text.append(f'{e_txt}^{{{lim_txt}}}')
            elif tag == 'drawing':
                import re
                from lxml import etree
                xml_str = etree.tostring(node).decode('utf-8', errors='ignore')
                m = re.search(r'embed="([^"]+)"', xml_str)
                if m:
                    rid = m.group(1)
                    part = doc.part.related_parts.get(rid)
                    if part and 'image' in part.content_type:
                        ext = part.content_type.split('/')[-1]
                        import os
                        from pathlib import Path
                        img_dir = Path(docx_path).parent / f"{Path(docx_path).stem}_images"
                        img_dir.mkdir(exist_ok=True, parents=True)
                        img_path = img_dir / f"img_{rid}.{ext}"
                        with open(img_path, 'wb') as f:
                            f.write(part.blob)
                        text.append(f"[IMG: {img_path.as_posix()}]")
            elif tag == 'oMath':
                inner_text = ''
                for child in node:
                    inner_text += extract_node(child)
                # Wrap in $ so that formula_render preserves the entire block as one equation
                text.append(f'${inner_text}$')
            else:
                for child in node:
                    text.append(extract_node(child))

            return ''.join(text)

    def iter_block_items(parent):
        if isinstance(parent, _Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        else:
            raise ValueError("unknown parent type")

        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    blocks = []
    block_id_counter = 1
    list_counters = {}

    def process_blocks(parent) -> list[DocumentBlock]:
        nonlocal block_id_counter
        local_blocks = []
        for i, item in enumerate(iter_block_items(parent)):
            if isinstance(item, Paragraph):
                text = extract_node(item._element).strip()
                
                numPr = item._element.xpath('.//w:numPr')
                if numPr:
                    numId_elem = numPr[0].xpath('.//w:numId/@w:val')
                    ilvl_elem = numPr[0].xpath('.//w:ilvl/@w:val')
                    if numId_elem:
                        numId = int(numId_elem[0])
                        ilvl = int(ilvl_elem[0]) if ilvl_elem else 0
                        key = (numId, ilvl)
                        
                        if key not in list_counters:
                            list_counters[key] = 1
                        else:
                            list_counters[key] += 1
                        
                        val = list_counters[key]
                        
                        # Reset sub-levels if we increment a higher level
                        # Specifically, if we increment ilvl 0, reset ilvl 1, 2 etc. for this numId
                        for lvl in range(ilvl + 1, 10):
                            if (numId, lvl) in list_counters:
                                del list_counters[(numId, lvl)]
                        
                        prefix = ""
                        if ilvl == 0:
                            prefix = f"{val}. "
                        elif ilvl == 1:
                            if val <= 26:
                                prefix = f"({chr(96+val)}) "
                            else:
                                prefix = f"({val}) "
                        elif ilvl >= 2:
                            romans = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]
                            if val <= 10:
                                prefix = f"({romans[val-1]}) "
                            else:
                                prefix = f"({val}) "
                                
                        text = prefix + text
                        
                if not text:
                    continue
                # Split by newline that might be produced by <w:br>
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                for line in lines:
                    b = DocumentBlock(
                        block_id=block_id_counter,
                        block_type="paragraph",
                        text=line,
                        order=block_id_counter
                    )
                    block_id_counter += 1
                    local_blocks.append(b)
            elif isinstance(item, Table):
                tbl_block = DocumentBlock(
                    block_id=block_id_counter,
                    block_type="table",
                    order=block_id_counter,
                    metadata={"rows": len(item.rows), "cols": len(item.columns)}
                )
                block_id_counter += 1
                
                for r_idx, row in enumerate(item.rows):
                    row_block = DocumentBlock(
                        block_id=block_id_counter,
                        block_type="table_row",
                        order=block_id_counter,
                        metadata={"row_index": r_idx}
                    )
                    block_id_counter += 1
                    
                    for c_idx, cell in enumerate(row.cells):
                        cell_block = DocumentBlock(
                            block_id=block_id_counter,
                            block_type="table_cell",
                            order=block_id_counter,
                            metadata={"row_index": r_idx, "col_index": c_idx}
                        )
                        block_id_counter += 1
                        
                        cell_content_blocks = process_blocks(cell)
                        cell_block.children = cell_content_blocks
                        cell_block.text = "\n".join(cb.text for cb in cell_content_blocks if cb.text)
                        
                        row_block.children.append(cell_block)
                    
                    tbl_block.children.append(row_block)
                local_blocks.append(tbl_block)
        return local_blocks

    blocks = process_blocks(doc)
    return blocks

def extract_lines(docx_path: str) -> list[str]:
    # fallback for backwards compatibility if needed
    blocks = extract_docx_blocks(docx_path)
    lines = []
    for b in blocks:
        if b.block_type == "paragraph":
            lines.extend([l.strip() for l in b.text.split("\n") if l.strip()])
        elif b.block_type == "table":
            for r in b.children:
                for c in r.children:
                    lines.extend([l.strip() for l in c.text.split("\n") if l.strip()])
    return lines

if __name__ == "__main__":
    import sys
    for b in extract_docx_blocks(sys.argv[1]):
        print(b.block_type, b.text[:50])
