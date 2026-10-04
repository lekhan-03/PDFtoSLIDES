def apply_corrections(parsed_list: list[dict], corrections_dict: dict) -> list[dict]:
    for item in parsed_list:
        if not item.get("question"):
            continue
        
        if "options" not in item:
            item["options"] = {}
            
        # Apply ID-based corrections
        item_id = str(item.get("id", ""))
        if item_id in corrections_dict:
            corr = corrections_dict[item_id]
            if "options" in corr:
                item["options"].update(corr["options"])
            if "question" in corr:
                item["question"] = corr["question"]
            if "question_type" in corr:
                item["question_type"] = corr["question_type"]
            if "parsed_ok" in corr:
                item["parsed_ok"] = corr["parsed_ok"]
                
        # Apply Match-based corrections
        # Ensure we don't accidentally match by a string like "41." because the id is "41"
        for corr in corrections_dict.values():
            match_str = corr.get("match")
            # If match_str is provided, see if the question text contains it anywhere.
            if match_str and match_str in item.get("question", ""):
                if "options" in corr:
                    item["options"].update(corr["options"])
                if "question" in corr:
                    item["question"] = corr["question"]
                if "question_type" in corr:
                    item["question_type"] = corr["question_type"]
                if "parsed_ok" in corr:
                    item["parsed_ok"] = corr["parsed_ok"]
                    
    return parsed_list
