import json

with open("data/outputs/chemistry_2026_10_03_130427.json", "r", encoding="utf-8") as f:
    old_data = json.load(f)
with open("data/outputs/chemistry_v3.json", "r", encoding="utf-8") as f:
    new_data = json.load(f)

old_dict = {str(item.get("id")): item for item in old_data}
new_dict = {str(item.get("id")): item for item in new_data}

diff_count = 0
for k, new_item in new_dict.items():
    old_item = old_dict.get(k)
    if not old_item:
        continue
    if new_item.get("options") != old_item.get("options") or new_item.get("question_type") != old_item.get("question_type"):
        diff_count += 1

print(f"Number of items whose options or type differ: {diff_count}")

ids_to_print = [11, 23, 30, 35, 41, 42, 44, 52]
for i in ids_to_print:
    k = str(i)
    print(f"\nID {i}")
    old_item = old_dict.get(k)
    new_item = new_dict.get(k)
    if old_item:
        print(f"OLD type: {old_item.get('question_type')} | options: {json.dumps(old_item.get('options'), ensure_ascii=False)}")
        print(f"OLD stem: {old_item.get('question')}")
    if new_item:
        print(f"NEW type: {new_item.get('question_type')} | options: {json.dumps(new_item.get('options'), ensure_ascii=False)}")
        print(f"NEW stem: {new_item.get('question')}")
