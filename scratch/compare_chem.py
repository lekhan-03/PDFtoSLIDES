import json

old_file = 'data/outputs/chemistry_2026_10_03_130427.json'
new_file = 'data/outputs/chemistry_new.json'

with open(old_file, 'r', encoding='utf-8') as f:
    old_data = json.load(f)
with open(new_file, 'r', encoding='utf-8') as f:
    new_data = json.load(f)

old_dict = {q['id']: q for q in old_data}
new_dict = {q['id']: q for q in new_data}

print("=== Options of Q33 ===")
print("OLD:")
print(json.dumps(old_dict.get(33, {}).get("options", {}), indent=2, ensure_ascii=False))
print("NEW:")
print(json.dumps(new_dict.get(33, {}).get("options", {}), indent=2, ensure_ascii=False))

print("\n=== Options of Q52 ===")
print("OLD:")
print(json.dumps(old_dict.get(52, {}).get("options", {}), indent=2, ensure_ascii=False))
print("NEW:")
print(json.dumps(new_dict.get(52, {}).get("options", {}), indent=2, ensure_ascii=False))

diffs = []
open_old = []
for q_id in sorted(old_dict.keys()):
    o = old_dict[q_id]
    n = new_dict.get(q_id)
    if not n: continue
    
    if o.get("question_type") == "open":
        open_old.append(q_id)
        
    old_opt = o.get("options", {})
    new_opt = n.get("options", {})
    
    if old_opt != new_opt or o.get("question_type") != n.get("question_type"):
        diffs.append((q_id, o, n))

print(f"\n=== Number of questions whose options or type changed: {len(diffs)} ===")
for q_id, o, n in diffs[:5]:
    print(f"\nID {q_id}")
    print(f"OLD type: {o.get('question_type')} | options: {json.dumps(o.get('options', {}), ensure_ascii=False)}")
    print(f"NEW type: {n.get('question_type')} | options: {json.dumps(n.get('options', {}), ensure_ascii=False)}")

print("\n=== Six OPEN ids in baseline and what they are now ===")
for q_id in open_old:
    n = new_dict.get(q_id)
    print(f"ID {q_id}: was {old_dict[q_id].get('question_type')}, now {n.get('question_type')} (parsed_ok: {n.get('parsed_ok')})")
    
print("\n=== All IDs whose type or option text differs ===")
print([d[0] for d in diffs])
