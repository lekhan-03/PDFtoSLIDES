from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from pathlib import Path
from src.document_model import DocumentBlock, InlineContent

def extract_docx_blocks(docx_path: str) -> list[DocumentBlock]:
    doc = Document(docx_path)
    M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    
    from src.pdf_spans import _SUP_CH, _SUB_CH, _script

    def extract_node(node):
            text = []
            tag = node.tag.split('}')[-1]
            in_math = tag in ('oMath', 'oMathPara') or any(
                ancestor.tag.split('}')[-1] in ('oMath', 'oMathPara')
                for ancestor in node.iterancestors()
            )

            if tag == 't':
                text.append(node.text or '')
            elif tag == 'tab':
                text.append('\t')
            elif tag == 'r':
                rPr = node.find(f'{W_NS}rPr')
                vert_align = None
                if rPr is not None:
                    va = rPr.find(f'{W_NS}vertAlign')
                    if va is not None:
                        vert_align = va.attrib.get(f'{W_NS}val')
                run_text = ''.join(extract_node(c) for c in node if c.tag.split('}')[-1] != 'rPr')
                if not in_math and vert_align == 'superscript':
                    return _script(run_text, _SUP_CH, "^")
                elif not in_math and vert_align == 'subscript':
                    return _script(run_text, _SUB_CH, "_")
                return run_text
            elif tag == 'f':
                num = node.find(f'./{M_NS}num')
                if num is None: num = node.find(f'{M_NS}num')
                den = node.find(f'./{M_NS}den')
                if den is None: den = node.find(f'{M_NS}den')
                n_txt = extract_node(num).strip() if num is not None else ''
                d_txt = extract_node(den).strip() if den is not None else ''
                # Keep the fraction as a structured math token for later
                # normalization instead of flattening it into ambiguous text.
                text.append(f'\\frac{{{n_txt}}}{{{d_txt}}}')
            elif tag == 'sSup':
                e = node.find(f'./{M_NS}e')
                if e is None: e = node.find(f'{M_NS}e')
                sup = node.find(f'./{M_NS}sup')
                if sup is None: sup = node.find(f'{M_NS}sup')
                e_txt = extract_node(e).strip() if e is not None else ''
                sup_txt = extract_node(sup).strip() if sup is not None else ''
                text.append(f'{e_txt}^{{{sup_txt}}}')
            elif tag == 'sSub':
                e = node.find(f'./{M_NS}e')
                if e is None: e = node.find(f'{M_NS}e')
                sub = node.find(f'./{M_NS}sub')
                if sub is None: sub = node.find(f'{M_NS}sub')
                e_txt = extract_node(e).strip() if e is not None else ''
                sub_txt = extract_node(sub).strip() if sub is not None else ''
                text.append(f'{e_txt}_{{{sub_txt}}}')
            elif tag == 'sSubSup':
                e = node.find(f'./{M_NS}e')
                if e is None: e = node.find(f'{M_NS}e')
                sub = node.find(f'./{M_NS}sub')
                if sub is None: sub = node.find(f'{M_NS}sub')
                sup = node.find(f'./{M_NS}sup')
                if sup is None: sup = node.find(f'{M_NS}sup')
                e_txt = extract_node(e).strip() if e is not None else ''
                sub_txt = extract_node(sub).strip() if sub is not None else ''
                sup_txt = extract_node(sup).strip() if sup is not None else ''
                text.append(f'{e_txt}_{{{sub_txt}}}^{{{sup_txt}}}')
            elif tag == 'rad':
                deg = node.find(f'./{M_NS}deg')
                if deg is None: deg = node.find(f'{M_NS}deg')
                e = node.find(f'./{M_NS}e')
                if e is None: e = node.find(f'{M_NS}e')
                deg_txt = extract_node(deg).strip() if deg is not None else ''
                e_txt = extract_node(e).strip() if e is not None else ''
                if deg_txt:
                    text.append(f'root({deg_txt}, {e_txt})')
                else:
                    text.append(f'sqrt({e_txt})')
            elif tag == 'nary':
                pr = node.find(f'./{M_NS}naryPr')
                if pr is None: pr = node.find(f'{M_NS}naryPr')
                chr_val = '∫' # default n-ary char is integral
                if pr is not None:
                    chr_elem = pr.find(f'./{M_NS}chr')
                    if chr_elem is None: chr_elem = pr.find(f'{M_NS}chr')
                    if chr_elem is not None:
                        chr_val = chr_elem.attrib.get(f'{M_NS}val', '∫')

                sub = node.find(f'./{M_NS}sub')
                if sub is None: sub = node.find(f'{M_NS}sub')
                sup = node.find(f'./{M_NS}sup')
                if sup is None: sup = node.find(f'{M_NS}sup')
                e = node.find(f'./{M_NS}e')
                if e is None: e = node.find(f'{M_NS}e')

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
                pr = node.find(f'./{M_NS}dPr')
                if pr is None: pr = node.find(f'{M_NS}dPr')
                beg = '('
                end = ')'
                if pr is not None:
                    b = pr.find(f'./{M_NS}begChr')
                    if b is None: b = pr.find(f'{M_NS}begChr')
                    if b is not None: beg = b.attrib.get(f'{M_NS}val', '(')
                    e = pr.find(f'./{M_NS}endChr')
                    if e is None: e = pr.find(f'{M_NS}endChr')
                    if e is not None: end = e.attrib.get(f'{M_NS}val', ')')

                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
                e_txt = extract_node(e_node) if e_node is not None else ''
                text.append(f'{beg}{e_txt}{end}')
            elif tag == 'br':
                text.append('\n')
            elif tag == 'acc':
                pr = node.find(f'./{M_NS}accPr')
                if pr is None: pr = node.find(f'{M_NS}accPr')
                chr_val = '̂'
                if pr is not None:
                    chr_elem = pr.find(f'./{M_NS}chr')
                    if chr_elem is None: chr_elem = pr.find(f'{M_NS}chr')
                    if chr_elem is not None:
                        chr_val = chr_elem.attrib.get(f'{M_NS}val', '̂')

                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
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
                pr = node.find(f'./{M_NS}barPr')
                if pr is None: pr = node.find(f'{M_NS}barPr')
                pos = 'top'
                if pr is not None:
                    pos_elem = pr.find(f'./{M_NS}pos')
                    if pos_elem is None: pos_elem = pr.find(f'{M_NS}pos')
                    if pos_elem is not None:
                        pos = pos_elem.attrib.get(f'{M_NS}val', 'top')

                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''

                if e_txt:
                    if pos == 'top':
                        text.append(f'\\overline{{{e_txt}}}')
                    else:
                        text.append(f'\\underline{{{e_txt}}}')
            elif tag == 'func':
                fname = node.find(f'./{M_NS}fName')
                if fname is None: fname = node.find(f'{M_NS}fName')
                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
                fname_txt = extract_node(fname).strip() if fname is not None else ''
                e_txt = extract_node(e_node).strip() if e_node is not None else ''
                # Output func like \sin{x} if standard, or just plain if unknown
                if fname_txt in ('sin', 'cos', 'tan', 'sec', 'cosec', 'cot', 'log', 'ln', 'exp'):
                    text.append(f'\\{fname_txt}{{{e_txt}}}')
                else:
                    text.append(f'{fname_txt}{{{e_txt}}}')
            elif tag == 'limLow':
                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
                lim = node.find(f'./{M_NS}lim')
                if lim is None: lim = node.find(f'{M_NS}lim')
                e_txt = extract_node(e_node).strip() if e_node is not None else ''
                lim_txt = extract_node(lim).strip() if lim is not None else ''
                text.append(f'{e_txt}_{{{lim_txt}}}')
            elif tag == 'limUpp':
                e_node = node.find(f'./{M_NS}e')
                if e_node is None: e_node = node.find(f'{M_NS}e')
                lim = node.find(f'./{M_NS}lim')
                if lim is None: lim = node.find(f'{M_NS}lim')
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

    def math_ir(node) -> InlineContent:
        """Represent OMML operands by their direct structural relationships."""
        from lxml import etree

        tag = node.tag.split('}')[-1]
        direct = {child.tag.split('}')[-1]: child for child in node}
        operand_roles = {
            'f': [('num', 'numerator'), ('den', 'denominator')],
            'sSup': [('e', 'base'), ('sup', 'superscript')],
            'sSub': [('e', 'base'), ('sub', 'subscript')],
            'sSubSup': [('e', 'base'), ('sub', 'subscript'), ('sup', 'superscript')],
            'rad': [('deg', 'degree'), ('e', 'radicand')],
            'nary': [('sub', 'lower_limit'), ('sup', 'upper_limit'), ('e', 'body')],
            'func': [('fName', 'function_name'), ('e', 'argument')],
            'd': [('e', 'contents')],
            'limLow': [('e', 'base'), ('lim', 'lower_limit')],
            'limUpp': [('e', 'base'), ('lim', 'upper_limit')],
            'acc': [('e', 'contents')],
            'bar': [('e', 'contents')],
        }
        type_names = {
            'f': 'fraction', 'sSup': 'superscript', 'sSub': 'subscript',
            'sSubSup': 'subsup', 'rad': 'radical', 'nary': 'nary',
            'func': 'function', 'd': 'delimiter', 'limLow': 'lower_limit',
            'limUpp': 'upper_limit', 'acc': 'accent', 'bar': 'bar',
            'oMath': 'math_sequence', 'oMathPara': 'math_sequence',
            'e': 'math_sequence', 'num': 'math_sequence', 'den': 'math_sequence',
            'sup': 'math_sequence', 'sub': 'math_sequence', 'deg': 'math_sequence',
            'lim': 'math_sequence',
            'matrix': 'matrix', 'mr': 'matrix_row', 'eqArr': 'equation_array',
            'groupChr': 'group',
        }

        children: list[InlineContent] = []
        if tag in operand_roles:
            for child_tag, role in operand_roles[tag]:
                child = direct.get(child_tag)
                if child is not None:
                    children.append(InlineContent(
                        kind=role,
                        value=extract_node(child),
                        children=[math_ir(child)],
                    ))
        elif tag in ('oMath', 'oMathPara', 'e', 'num', 'den', 'sup', 'sub', 'deg', 'lim'):
            for child in node:
                child_tag = child.tag.split('}')[-1]
                if child_tag.endswith('Pr') or child_tag in ('ctrlPr', 'argPr'):
                    continue
                children.append(math_ir(child))
        elif tag not in ('r', 't', 'chr', 'ctrlPr', 'argPr'):
            # Preserve matrix/piecewise and future OMML containers recursively.
            for child in node:
                child_tag = child.tag.split('}')[-1]
                if child_tag.endswith('Pr') or child_tag in ('ctrlPr', 'argPr'):
                    continue
                children.append(math_ir(child))

        value = extract_node(node)
        if tag == 'r':
            value = ''.join(child.text or '' for child in node.iter()
                            if child.tag == f'{M_NS}t')
        formatting = {}
        if tag == 'nary':
            props = direct.get('naryPr')
            char_node = next((c for c in props if c.tag == f'{M_NS}chr'), None) if props is not None else None
            if char_node is not None:
                formatting['operator'] = char_node.get(f'{M_NS}val')
        source = {"omml_tag": tag}
        if tag in ('oMath', 'oMathPara'):
            source_math = etree.fromstring(etree.tostring(node))
            # Word occasionally stores arithmetic operators as ordinary m:r
            # runs with w:vertAlign=subscript/superscript. That is visual run
            # formatting, not an OMML script operand; applying it to + or −
            # corrupts both the canonical compatibility string and native PPTX.
            operator_tokens = {"+", "-", "−", "×", "÷", "=", "<", ">", "≤", "≥", "±", "∓"}
            for run in source_math.xpath(".//*[local-name()='r']"):
                run_text = "".join(run.xpath(".//*[local-name()='t']/text()")).strip()
                if run_text not in operator_tokens:
                    continue
                for alignment in run.xpath(".//*[local-name()='vertAlign']"):
                    alignment.getparent().remove(alignment)
            source["omml"] = etree.tostring(source_math, encoding='unicode')
        return InlineContent(
            kind=type_names.get(tag, 'math_token'),
            value=value,
            children=children,
            source=source,
            formatting=formatting,
        )

    def extract_inline_content(paragraph_element) -> list[InlineContent]:
        """Extract ordered text, formatting, math, media, and break nodes."""
        content: list[InlineContent] = []

        def walk(node):
            tag = node.tag.split('}')[-1]
            if tag in ('pPr', 'rPr', 'proofErr', 'bookmarkStart', 'bookmarkEnd'):
                return
            if tag in ('oMath', 'oMathPara'):
                content.append(math_ir(node))
                return
            if tag == 'r':
                rpr = node.find(f'{W_NS}rPr')
                vert = None
                formatting = {}
                if rpr is not None:
                    va = rpr.find(f'{W_NS}vertAlign')
                    if va is not None:
                        val = va.get(f'{W_NS}val')
                        vert = {'superscript': 'superscript',
                                'subscript': 'subscript'}.get(val)
                    for xml_name, key in (('b', 'bold'), ('i', 'italic'), ('u', 'underline')):
                        item = rpr.find(f'{W_NS}{xml_name}')
                        if item is not None:
                            formatting[key] = item.get(f'{W_NS}val', '1') not in ('0', 'false', 'none')
                for child in node:
                    child_tag = child.tag.split('}')[-1]
                    if child_tag == 'rPr':
                        continue
                    if child_tag == 't':
                        content.append(InlineContent(kind='text', value=child.text or '',
                                                     vertical_align=vert, formatting=dict(formatting)))
                    elif child_tag == 'tab':
                        content.append(InlineContent(kind='text', value='\t', formatting=dict(formatting)))
                    elif child_tag == 'br':
                        content.append(InlineContent(kind='line_break', formatting=dict(formatting)))
                    elif child_tag in ('drawing', 'pict'):
                        marker = extract_node(child)
                        path = marker[marker.find('[IMG:') + 5:marker.rfind(']')].strip() if '[IMG:' in marker else marker
                        content.append(InlineContent(kind='image', value=path,
                                                     source={"relationship_xml": child.xml}))
                    else:
                        walk(child)
                return
            if tag == 'br':
                content.append(InlineContent(kind='line_break'))
                return
            if tag == 'tab':
                content.append(InlineContent(kind='text', value='\t'))
                return
            if tag in ('drawing', 'pict'):
                marker = extract_node(node)
                path = marker[marker.find('[IMG:') + 5:marker.rfind(']')].strip() if '[IMG:' in marker else marker
                content.append(InlineContent(kind='image', value=path))
                return
            for child in node:
                walk(child)

        walk(paragraph_element)
        return content

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
                inline_content = extract_inline_content(item._element)
                
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
                import re
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                if not lines:
                    continue

                structural_re = re.compile(r'^(?:\d+[\.\)]|[A-Ea-e][\.\)]|\([A-Ea-e]\)|\([i-xIvX]+\))\s+')
                has_multiple_structures = sum(1 for line in lines if structural_re.match(line)) > 1

                if has_multiple_structures:
                    grouped_lines = []
                    curr = ""
                    for line in lines:
                        if structural_re.match(line):
                            if curr: grouped_lines.append(curr)
                            curr = line
                        else:
                            curr = (curr + "\n" + line).strip() if curr else line
                    if curr: grouped_lines.append(curr)
                else:
                    grouped_lines = ["\n".join(lines)]

                paragraph_source_id = block_id_counter
                for part_index, line in enumerate(grouped_lines):
                    inline_part = inline_content if part_index == 0 else []
                    legacy_runs = [{"type": run.kind, "text": run.value,
                                    "math": run.kind.startswith('math') or run.kind in (
                                        'fraction', 'superscript', 'subscript', 'radical',
                                        'function', 'nary', 'subsup'),
                                    "vertical_align": run.vertical_align,
                                    **run.formatting}
                                   for run in inline_part]
                    b = DocumentBlock(
                        block_id=block_id_counter,
                        block_type="paragraph",
                        text=line,
                        order=block_id_counter,
                        metadata={"source_paragraph_id": paragraph_source_id,
                                  "source_part": part_index},
                        runs=legacy_runs,
                        inline_content=inline_part,
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
