def group_by_y_overlap(spans_and_drawings):
    # Each item has bbox (x0, y0, x1, y1)
    # We want to partition them into groups where items in a group transitively overlap in Y.
    
    # Sort items by y0
    sorted_items = sorted(spans_and_drawings, key=lambda i: i['bbox'][1])
    
    groups = []
    if not sorted_items:
        return groups
        
    current_group = [sorted_items[0]]
    current_y0 = sorted_items[0]['bbox'][1]
    current_y1 = sorted_items[0]['bbox'][3]
    
    for item in sorted_items[1:]:
        y0 = item['bbox'][1]
        y1 = item['bbox'][3]
        
        # Overlap condition: max(current_y0, y0) <= min(current_y1, y1)
        # But wait, usually we want some minimum overlap, or just any overlap?
        # A tiny overlap (e.g. 1 pixel) might merge separate lines if lines are too close.
        # Let's use a small threshold, or strictly <.
        if y0 <= current_y1: # overlap exists
            current_group.append(item)
            current_y1 = max(current_y1, y1)
        else:
            groups.append(current_group)
            current_group = [item]
            current_y0 = y0
            current_y1 = y1
            
    if current_group:
        groups.append(current_group)
        
    return groups

# Test it
items = [
    {'type': 'text', 'text': 'The integral of', 'bbox': (50, 100, 150, 120)},
    {'type': 'text', 'text': 'dx', 'bbox': (160, 90, 180, 105)}, # num
    {'type': 'draw', 'bbox': (155, 110, 185, 111)}, # bar
    {'type': 'text', 'text': '(1+x^2)', 'bbox': (155, 115, 200, 130)}, # den
    {'type': 'text', 'text': 'is evaluated.', 'bbox': (210, 100, 300, 120)},
    
    # next line
    {'type': 'text', 'text': 'Next line.', 'bbox': (50, 140, 150, 160)},
]

for i, g in enumerate(group_by_y_overlap(items)):
    print(f"Group {i+1}:")
    for item in g:
        print("  ", item)
