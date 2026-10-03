"""Extract clean text lines from a .docx file."""
from docx import Document


def extract_lines(docx_path: str) -> list[str]:
    """Return a flat list of cleaned, non-empty paragraph lines from the
    document, in reading order. Table cells are included too.
    Properly extracts OMML math equations (fractions, sub/superscripts)."""
    doc = Document(docx_path)
    lines = []
    
    M_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
    
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

    for para in doc.paragraphs:
        line = " ".join(extract_node(para._element).split())
        if line:
            lines.append(line)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    line = " ".join(extract_node(para._element).split())
                    if line:
                        lines.append(line)

    return lines


if __name__ == "__main__":
    import sys
    for l in extract_lines(sys.argv[1]):
        print(l)
