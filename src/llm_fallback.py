"""LLM fallback for MCQ blocks the regex parser couldn't confidently split.

Minimal-token design:
- Only called for blocks that FAILED regex parsing (usually a handful, not all).
- ALL failed blocks are sent in a SINGLE Groq request, never one call per question.
- The prompt requests compact JSON only -- no prose, no markdown fences.
- If GROQ_API_KEY isn't set (or there's nothing to fix), this module is never
  invoked and the pipeline runs 100% regex with zero network calls.

Configuration (set in .env or as real env vars):
    GROQ_API_KEY   - required  (free tier: https://console.groq.com)
    GROQ_MODEL     - optional model override
                     default: llama-3.3-70b-versatile
                     alternatives: llama3-8b-8192 | mixtral-8x7b-32768 | gemma2-9b-it

Note: python-dotenv loads .env before this module is ever imported (in main.py),
so os.environ.get() here always sees the values from the .env file.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a precise data-extraction assistant. Your ONLY job is to parse raw MCQ text.

Rules:
1. Output ONLY valid JSON -- no prose, no markdown, no code fences.
2. Return a JSON array (list) of objects, one per question.
3. Each object must have exactly these keys:
   "id"       : integer (the question number given in input)
   "question" : string  (the question stem, without option labels)
   "options"  : object  with keys "A", "B", "C", "D" (string values)
4. If a question has fewer than 4 options, use an empty string "" for missing ones.
5. Do NOT add any explanation, commentary, or wrapper keys.

Output format (strict):
[{"id": 1, "question": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}}, ...]
"""

USER_PROMPT_TEMPLATE = """\
Parse the following MCQ blocks and return a JSON array as instructed.

{blocks}
"""

_DEFAULT_MODEL = "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_model() -> str:
    """Read model from env at call-time (after dotenv has been loaded)."""
    return os.environ.get("GROQ_MODEL", _DEFAULT_MODEL)


def _build_user_prompt(failed_blocks: list[dict]) -> str:
    lines = []
    for b in failed_blocks:
        lines.append(f"[Question {b['id']}]")
        lines.append(" ".join(b["lines"]) if "lines" in b else (b.get("question") or ""))
        lines.append("")          # blank separator
    return USER_PROMPT_TEMPLATE.format(blocks="\n".join(lines))


def _repair_truncated_json(text: str) -> list | None:
    """Try to close a truncated JSON array by appending closing suffixes.

    When max_tokens is exhausted mid-generation, the array is cut off somewhere
    inside the last element.  We try progressively more complete suffixes until
    json.loads() accepts the result.

    Returns the parsed list on success, or None if all attempts fail.
    """
    start = text.find("[")
    if start == -1:
        return None

    partial = text[start:].rstrip().rstrip(",")  # drop trailing comma if present

    # Each string below is the literal characters to append.
    # Coverage: value-string closed / not closed, 1 or 2 unclosed braces.
    #
    #   "}]"       -- value already closed, missing: close-obj, close-array
    #   "}}]"      -- value closed, missing: close-options-obj, close-q-obj, close-array
    #   '"}}]'     -- value not closed, missing: close-quote, ..., close-array
    #   '"}]'      -- value not closed, missing: close-quote, close-obj, close-array
    #   '"}}}'     -- edge case: 3 levels
    closings: list[str] = [
        "]",
        "}]",
        "}}]",
        '"}}]',
        '"}]',
        '"}}}]',
    ]

    for suffix in closings:
        try:
            obj = json.loads(partial + suffix)
            if isinstance(obj, list) and obj:
                return obj
        except json.JSONDecodeError:
            continue

    return None


def _extract_json_array(text: str) -> list:
    """Robustly extract a JSON array from model output that may contain
    markdown fences, a wrapper object, extra prose, or a truncated tail."""

    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip().removesuffix("```").strip()

    # 1. Direct parse -- ideal path
    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("questions", "results", "data", "items", "mcqs"):
                if isinstance(obj.get(key), list):
                    return obj[key]
    except json.JSONDecodeError:
        pass

    # 2. Embedded array inside prose
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 3. Repair a truncated array (max_tokens cutoff)
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        return repaired

    raise ValueError(
        f"Could not extract a valid JSON array from model response:\n{text[:800]}"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fix_with_llm(failed_blocks: list[dict]) -> list[dict]:
    """Send ALL failed blocks in one Groq request.

    Returns a list of fixed question dicts with the same shape as a
    parser.parse_block() success.  Raises RuntimeError / ImportError when
    prerequisites are missing.
    """
    if not failed_blocks:
        return []

    # Validate prerequisites
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "gsk_your_key_here":
        raise RuntimeError(
            "GROQ_API_KEY is not set (or still has the placeholder value).\n"
            "Edit .env, set GROQ_API_KEY to your real key, and re-run.\n"
            "Free key: https://console.groq.com"
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise ImportError(
            "The 'groq' package is not installed.\n"
            "Run:  pip install groq"
        ) from exc

    model = _get_model()
    client = Groq(api_key=api_key)
    user_prompt = _build_user_prompt(failed_blocks)

    # We do NOT use response_format={"type": "json_object"}.
    # That Groq mode rejects requests whose input contains special characters
    # (chemical formulas, brackets, Greek letters) with 400 json_validate_failed.
    # We extract JSON ourselves via _extract_json_array().
    def _call(prompt: str, extra_tokens: int = 0) -> str:
        # 1500 tokens per block handles long match-the-column option strings.
        budget = 1500 * len(failed_blocks) + 500 + extra_tokens
        response = client.chat.completions.create(
            model=model,
            max_tokens=budget,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0,
        )
        return response.choices[0].message.content.strip()

    # First attempt
    raw = _call(user_prompt)
    try:
        payload = _extract_json_array(raw)
    except ValueError:
        is_truncated = raw.lstrip().startswith("[")
        if is_truncated:
            print("    [retry] Response truncated -- retrying with higher token budget ...")
            raw2 = _call(user_prompt, extra_tokens=2000)
        else:
            print("    [retry] Response was not clean JSON -- retrying with simplified prompt ...")
            raw2 = _call(
                "Return ONLY a JSON array -- no explanation, no fences.\n"
                'Each element: {"id": <int>, "question": "<stem>", '
                '"options": {"A": "", "B": "", "C": "", "D": ""}}.\n\n'
                + user_prompt,
                extra_tokens=1000,
            )
        try:
            payload = _extract_json_array(raw2)
        except ValueError:
            # Last resort: one block at a time
            print("    [retry] Batch failed -- processing blocks individually ...")
            payload = []
            for block in failed_blocks:
                single_raw = _call(_build_user_prompt([block]), extra_tokens=500)
                try:
                    payload.extend(_extract_json_array(single_raw))
                except ValueError:
                    print(f"    [skip]  Could not parse block id={block['id']}")
                    payload.append({
                        "id":       block["id"],
                        "question": " ".join(block["lines"]),
                        "options":  {},
                    })

    # Build output dicts
    section_by_id = {b["id"]: b["section"] for b in failed_blocks}
    out: list[dict] = []
    for item in payload:
        out.append({
            "id":           item["id"],
            "section":      section_by_id.get(item["id"]),
            "question":     item.get("question", ""),
            "options":      item.get("options", {}),
            "answer":       None,
            "parsed_ok":    True,
            "fixed_by_llm": True,
            "llm_model":    model,
        })
    return out


@dataclass
class RecoveryContext:
    question_id: Any
    section: str = "General"
    source_question_number: str | None = None
    question: str = ""
    options: dict[str, str] = field(default_factory=dict)
    question_type: str = "unknown"
    source_blocks: list[dict] = field(default_factory=list)
    inline_content: list[dict] = field(default_factory=list)


@dataclass
class RecoveryProposal:
    question_id: Any
    question: str
    options: dict[str, str]
    extra_fields: dict[str, Any] = field(default_factory=dict)


class LLMRecoveryProvider(Protocol):
    def recover_questions(self, contexts: list[RecoveryContext]) -> list[RecoveryProposal | dict]: ...


class GroqRecoveryProvider:
    """Provider adapter; parser and recovery validation do not depend on Groq."""
    def __init__(self, api_key: str, model: str):
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model = model

    def recover_questions(self, contexts: list[RecoveryContext]) -> list[dict]:
        context_payload = [{
            "id": context.question_id,
            "question": context.question,
            "options": context.options,
            "question_type": context.question_type,
            "section": context.section,
            "source_question_number": context.source_question_number,
            "source_blocks": context.source_blocks,
            "inline_content": context.inline_content,
        } for context in contexts]
        prompt = (
            "Return a JSON array with one recovery proposal for each input id. "
            "Each proposal may contain only id, question, and options. Preserve the supplied source. "
            "Do not invent missing options or metadata. Non-MCQ items use an empty options object.\n\n"
            + json.dumps(context_payload, ensure_ascii=False)
        )
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1000 * len(contexts) + 500,
            messages=[
                {"role": "system", "content": "Recover ambiguous exam questions. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return _extract_json_array(response.choices[0].message.content.strip())


def recover_questions_batch(
    questions: list[dict], provider: LLMRecoveryProvider | None = None,
) -> list[dict]:
    """Propose recoveries for failed items; canonical validation remains downstream."""
    failed = [q for q in questions if not q.get("parsed_ok") or q.get("needs_review")]
    if not failed:
        return questions

    if provider is None:
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key or api_key == "gsk_your_key_here":
            print("    [!] GROQ_API_KEY not configured. Skipping LLM recovery.")
            for question in failed:
                question.setdefault("recovery_diagnostics", []).append({
                    "status": "skipped", "reason": "provider_not_configured",
                    "question_id": question.get("id"),
                })
            return questions
        model = os.environ.get("MCQ_LLM_MODEL") or os.environ.get("GROQ_MODEL") or _DEFAULT_MODEL
        try:
            provider = GroqRecoveryProvider(api_key, model)
        except ImportError:
            print("    [!] groq package not installed. Skipping LLM recovery.")
            return questions

    contexts = []
    question_by_id = {}
    for index, question in enumerate(failed):
        question_id = question.get("id", f"recovery-{index + 1}")
        key = str(question_id)
        if key in question_by_id:
            key = f"{key}#{index + 1}"
        question_by_id[key] = question
        contexts.append(RecoveryContext(
            question_id=key,
            section=question.get("section") or "General",
            source_question_number=question.get("source_question_number"),
            question=str(question.get("question") or ""),
            options=question.get("options") if isinstance(question.get("options"), dict) else {},
            question_type=question.get("question_type") or "unknown",
            source_blocks=question.get("source_blocks", []),
            inline_content=question.get("inline_content", []),
        ))

    try:
        proposals = provider.recover_questions(contexts)
        if not isinstance(proposals, list):
            raise ValueError("provider must return a JSON array of recovery proposals")
    except Exception as exc:
        print(f"    [!] LLM recovery attempt failed: {exc}")
        for question in failed:
            question.setdefault("recovery_diagnostics", []).append({
                "status": "failed", "reason": "provider_error",
                "question_id": question.get("id"), "exception": repr(exc),
                "fallback": "retain deterministic parse and validation result",
            })
            validation = question.setdefault("validation", {})
            validation.setdefault("base_needs_review", False)
            validation["base_needs_review"] = True
            issues = validation.setdefault("source_issues", [])
            if "LLM_PROVIDER_ERROR" not in issues:
                issues.append("LLM_PROVIDER_ERROR")
        return questions

    seen_ids = set()
    for raw in proposals if isinstance(proposals, list) else []:
        if isinstance(raw, RecoveryProposal):
            proposal = raw
            extra_fields = proposal.extra_fields
        elif isinstance(raw, dict):
            extra_fields = set(raw) - {"id", "question", "options"}
            if ("id" not in raw or not isinstance(raw.get("question"), str)
                    or not isinstance(raw.get("options"), dict)):
                extra_fields = set(extra_fields) | {"__schema_error__"}
            proposal = RecoveryProposal(
                question_id=raw.get("id"),
                question=raw.get("question") if isinstance(raw.get("question"), str) else "",
                options=raw.get("options") if isinstance(raw.get("options"), dict) else {},
                extra_fields={key: raw[key] for key in extra_fields},
            )
        else:
            continue

        key = str(proposal.question_id)
        question = question_by_id.get(key)
        if question is None or key in seen_ids:
            continue
        seen_ids.add(key)

        qtype = str(question.get("question_type") or "").lower()
        is_mcq = qtype in ("mcq", "multiple_correct", "statement_based", "assertion_reason", "match_list") or bool(question.get("options"))
        labels = {str(k).strip().upper(): str(v).strip() for k, v in proposal.options.items()}
        valid = bool(proposal.question.strip()) and not extra_fields
        valid = valid and set(labels) <= {"A", "B", "C", "D", "E"} and all(labels.values())
        if is_mcq:
            valid = valid and all(labels.get(label) for label in ("A", "B", "C", "D"))
        if not valid:
            validation = question.setdefault("validation", {})
            validation.setdefault("base_needs_review", False)
            validation["base_needs_review"] = True
            validation.setdefault("source_issues", []).append("LLM_PROPOSAL_INVALID_OR_INCOMPLETE")
            question.setdefault("recovery_diagnostics", []).append({
                "status": "rejected", "reason": "invalid_or_incomplete_proposal",
                "question_id": question.get("id"),
                "unexpected_fields": sorted(extra_fields),
                "fallback": "retain deterministic parse and validate it",
            })
            continue

        question["question"] = proposal.question.strip()
        question["options"] = labels
        question["recovered_by_llm"] = True
        question["llm_model"] = getattr(provider, "model", "configured-provider")
        question.setdefault("recovery_diagnostics", []).append({
            "status": "proposal_applied", "question_id": question.get("id"),
            "provider": type(provider).__name__,
        })

    return questions
