import json

data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))

print("--- Print the type and options of ids 55, 118, 155, 172 and 194 ---")
for q in data:
    if q.get('id') in [55, 118, 155, 172, 194]:
        print(f"ID {q['id']} Type: {q.get('question_type')}")
        print(f"Options: {q.get('options')}")

print("\n--- List the 3 open questions in the deck (id, full text) ---")
for q in data:
    if q.get('question_type') == 'open':
        print(f"ID {q['id']}: {q['question']}")

print("\n--- Explain 191 + 3 + 2 = 196 versus highest question number 195 ---")
# Find duplicates
seen = set()
dups = set()
for q in data:
    qid = q.get('id')
    if qid is not None:
        if qid in seen:
            dups.add(qid)
        seen.add(qid)
        
print(f"IDs that are duplicated: {sorted(list(dups))}")
