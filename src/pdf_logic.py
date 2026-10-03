import re

def rebuild_group(group):
    text_items = [i for i in group if i['type'] == 'text']
    draw_items = [i for i in group if i['type'] == 'draw']
    
    # Process \sqrt
    # A \sqrt is a text item '√' followed by a horizontal bar over some text.
    # Actually, let's just find the horizontal bar that has nothing above it, and text below it, 
    # and maybe a '√' to its left.
    for draw in draw_items[:]:
        dx0, dy0, dx1, dy1 = draw['bbox']
        
        above = []
        below = []
        others = []
        
        for t in text_items:
            tx0, ty0, tx1, ty1 = t['bbox']
            tx_c = (tx0 + tx1) / 2
            
            # Allow some overflow for text bounds
            if dx0 - 15 <= tx_c <= dx1 + 15:
                if ty1 <= dy0 + 5: 
                    above.append(t)
                elif ty0 >= dy1 - 5: 
                    below.append(t)
                else:
                    others.append(t)
            else:
                others.append(t)
                
        if not above and below:
            # Could be a sqrt
            # Check if there is a root symbol to the left
            root_item = next((t for t in others if '√' in t['text'] and abs(t['bbox'][2] - dx0) < 15), None)
            if root_item:
                below_text = "".join([t['text'] for t in sorted(below, key=lambda i: i['bbox'][0])])
                new_text = f"\\sqrt{{{below_text}}}"
                
                new_item = {
                    'type': 'text',
                    'text': new_text,
                    'bbox': (root_item['bbox'][0], min([t['bbox'][1] for t in below]), dx1, max([t['bbox'][3] for t in below]))
                }
                others.remove(root_item)
                text_items = others + [new_item]
                draw_items.remove(draw)
                
    # Process fractions
    for draw in draw_items[:]:
        dx0, dy0, dx1, dy1 = draw['bbox']
        
        above = []
        below = []
        others = []
        
        for t in text_items:
            tx0, ty0, tx1, ty1 = t['bbox']
            tx_c = (tx0 + tx1) / 2
            
            if dx0 - 15 <= tx_c <= dx1 + 15:
                if ty1 <= dy0 + 5: 
                    above.append(t)
                elif ty0 >= dy1 - 5: 
                    below.append(t)
                else:
                    others.append(t)
            else:
                others.append(t)
                
        if above and below:
            above_text = "".join([t['text'] for t in sorted(above, key=lambda i: i['bbox'][0])])
            below_text = "".join([t['text'] for t in sorted(below, key=lambda i: i['bbox'][0])])
            frac_text = f"\\frac{{{above_text}}}{{{below_text}}}"
            
            new_item = {
                'type': 'text',
                'text': frac_text,
                'bbox': (dx0, min([t['bbox'][1] for t in above]), dx1, max([t['bbox'][3] for t in below]))
            }
            text_items = others + [new_item]
            draw_items.remove(draw)
            
    # Process Integrals (\int) limits
    # Find ∫
    for t in text_items[:]:
        if '∫' in t['text']:
            ix0, iy0, ix1, iy1 = t['bbox']
            
            # Find limits: text items directly to the right of ∫, small width, above/below center
            # Actually, sometimes they are slightly above/below.
            ic_y = (iy0 + iy1) / 2
            
            upper = None
            lower = None
            others = []
            
            for o in text_items:
                if o == t: continue
                ox0, oy0, ox1, oy1 = o['bbox']
                
                # if right after ∫ and relatively close
                if 0 <= (ox0 - ix1) <= 15:
                    if oy1 <= ic_y + 3:
                        upper = o
                    elif oy0 >= ic_y - 3:
                        lower = o
                    else:
                        others.append(o)
                else:
                    others.append(o)
                    
            if upper or lower:
                # build \int_{lower}^{upper}
                res = "\\int"
                if lower: res += f"_{{{lower['text']}}}"
                if upper: res += f"^{{{upper['text']}}}"
                
                # replace t
                t['text'] = res
                
                if upper in text_items: text_items.remove(upper)
                if lower in text_items: text_items.remove(lower)

    text_items.sort(key=lambda i: i['bbox'][0])
    line_str = " ".join([t['text'] for t in text_items])
    return line_str
