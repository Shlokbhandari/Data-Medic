import json
import re
from llm import inference


PATCH_PROMPT_TEMPLATE = """You are a data pipeline engineer. You are given:
1. A diagnosis of a specific data quality issue found in a pipeline
2. The evidence (actual affected rows and column statistics)
3. The current full source code of the pipeline script

Your job is to propose a minimal, targeted code change to the pipeline script that fixes the diagnosed root cause — not just patches the symptom.

RULES:
- Only change what is necessary to fix THIS specific issue
- Do NOT rewrite unrelated parts of the file
- Do NOT remove existing cleaning logic for other issue types (e.g. dropping null prices, handling duplicates that already works)
- The fix should address the ROOT CAUSE described in the diagnosis, not just hide the symptom
- Keep the code simple and readable
{finding_specific_rules}

DIAGNOSIS:
Root cause: {root_cause}
Confidence: {confidence}
Reasoning: {reasoning}

EVIDENCE:
Issue: {issue}
Column: {column}
Total rows affected: {total_affected}
Affected rows: {affected_rows}
{stats_section}

CURRENT PIPELINE CODE:
```python
{current_code}
```

Respond with a JSON object containing exactly these fields:
- "explanation": plain English — why this specific code change addresses the diagnosed root cause, not just what it does
- "patched_code": the full corrected file content (complete file, not just a snippet), ready to replace the current file
- "risk_notes": anything you think a human reviewer should double-check before applying this patch

CRITICAL JSON FORMATTING RULE: Your response must be valid JSON. Inside the "patched_code" string, you MUST use single quotes for all Python strings (e.g. print('hello') not print("hello")), and use single quotes inside f-strings (e.g. f'Rows: {{len(df)}}' not f"Rows: {{len(df)}}"). This avoids breaking the JSON. Use double curly braces for f-string expressions inside JSON strings.

Respond with ONLY the JSON object, no other text before or after it."""


def _extract_field(text, field_name, next_field_name=None):
    """Pull a field value out of a JSON-like response when standard parsing fails."""
    pattern = f'"{field_name}"\\s*:\\s*"'
    match = re.search(pattern, text)
    if not match:
        return None

    start = match.end()

    if next_field_name:
        next_pattern = f'",\\s*"{next_field_name}"'
        next_match = re.search(next_pattern, text[start:])
        if next_match:
            return text[start:start + next_match.start()]

    # For the last field, find the closing quote before the final }
    end = text.rindex('"')
    return text[start:end]


def _parse_response(response_text, current_code):
    """Attempts to parse the LLM response as JSON, with fallbacks for common formatting issues."""

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

    # First try: standard JSON parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second try: extract from outermost braces
    try:
        start = cleaned.index('{')
        end = cleaned.rindex('}') + 1
        return json.loads(cleaned[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # Third try: regex extraction for each field individually
    # (handles f-string braces in patched_code that break JSON)
    explanation = _extract_field(cleaned, 'explanation', 'patched_code')
    patched_code = _extract_field(cleaned, 'patched_code', 'risk_notes')
    risk_notes = _extract_field(cleaned, 'risk_notes')

    if explanation and patched_code:
        return {
            'explanation': explanation,
            'patched_code': patched_code.strip().replace('\\n', '\n'),
            'risk_notes': risk_notes or 'No risk notes provided'
        }

    print(f"ERROR: Could not parse LLM response. Raw response:\n{response_text}")
    return {
        'explanation': 'Could not parse LLM response',
        'patched_code': current_code,
        'risk_notes': f'Raw response: {response_text}'
    }


def generate_patch(diagnosis, evidence, current_code, finding_type=None, extra_context=''):
    """Takes a diagnosis, evidence, and the current pipeline code, and asks the LLM
    to propose a specific code fix. Returns the patch dict and which backend answered.

    extra_context is optional feedback from a previous failed attempt,
    appended to the prompt so the LLM can learn from its mistakes."""

    finding = evidence['finding']

    stats_section = ""
    if 'column_stats' in evidence:
        s = evidence['column_stats']
        stats_section = f"Column stats from clean rows: min={s['min']}, max={s['max']}, mean={s['mean']}, median={s['median']}"

    finding_specific_rules = ""
    if finding_type == 'duplicate_transaction_id':
        finding_specific_rules = "- IMPORTANT FOR DUPLICATE KEY ISSUES: If the diagnosis indicates the pipeline already handles duplicates but the root cause is upstream data quality, the fix must still make row selection deterministic — sort by order_date (earliest first) before dropping duplicates, so the kept row is always the one with the earliest date."
    elif finding_type == 'suspicious_zero_price':
        finding_specific_rules = "- IMPORTANT FOR $0 PRICE ISSUES: You must NOT permanently drop rows with a price of exactly 0.0. Instead, you must isolate them: select the rows where price == 0.0, add a new column `flag_reason` set to 'suspicious zero price', write them to a new file 'data/flagged_orders.csv' (with index=False), and then exclude them from the main DataFrame before it is written to 'data/processed_orders.csv'."
    elif finding_type == 'missing_price':
        finding_specific_rules = "- IMPORTANT FOR MISSING PRICE ISSUES: The pipeline currently drops rows with a missing price. You must change this so the data is not silently lost. You must isolate them: select the rows where price is missing, add a new column `flag_reason` set to 'missing price', write them to a new file 'data/flagged_orders.csv' (with index=False, or append if it exists), and then exclude them from the main DataFrame before it is written to 'data/processed_orders.csv'."
    elif finding_type == 'baseline_drift':
        col = evidence.get('column', 'unknown')
        finding_specific_rules = (
            f"- IMPORTANT FOR BASELINE DRIFT / UNEXPECTED NULL ISSUES: The evidence contains ALL rows affected by this anomaly, not just a single row. "
            f"You must handle EVERY row listed in the evidence's affected rows. "
            f"For each affected row, isolate it: select ALL rows where the column '{col}' is null, "
            f"add a new column `flag_reason` set to 'baseline drift: unexpected nulls in {col}', "
            f"write ALL of them to 'data/flagged_orders.csv' (with index=False, or append if it already exists), "
            f"and then exclude ALL of them from the main DataFrame before it is written to 'data/processed_orders.csv'. "
            f"Do NOT handle only one row — you must catch every row where the column value is null."
        )

    prompt = PATCH_PROMPT_TEMPLATE.format(
        root_cause=diagnosis.get('root_cause', 'unknown'),
        confidence=diagnosis.get('confidence', 'N/A'),
        reasoning=diagnosis.get('reasoning', 'N/A'),
        issue=finding['issue'],
        column=evidence['column'],
        total_affected=evidence['total_affected_in_dataset'],
        affected_rows=evidence['affected_rows'],
        stats_section=stats_section,
        current_code=current_code,
        finding_specific_rules=finding_specific_rules,
    )

    if extra_context:
        prompt += f"\n\nIMPORTANT — YOUR PREVIOUS ATTEMPT FAILED. Here is what went wrong:\n{extra_context}\nFix this specific problem in your new attempt."

    response_text, backend = inference(prompt)
    patch = _parse_response(response_text, current_code)

    # Cheap syntax check before returning
    try:
        compile(patch['patched_code'], '<patched_code>', 'exec')
        patch['syntax_valid'] = True
        patch['syntax_error'] = None
    except SyntaxError as e:
        patch['syntax_valid'] = False
        patch['syntax_error'] = f"Line {e.lineno}: {e.msg}"

    return patch, backend

