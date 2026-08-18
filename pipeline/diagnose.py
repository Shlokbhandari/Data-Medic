import json
from llm import inference


DIAGNOSIS_PROMPT_TEMPLATE = """You are a data pipeline diagnostician. You are given evidence about a data quality issue found in a pipeline. Your job is to determine why this issue likely happened, based ONLY on the evidence provided. Do not invent or assume anything not present in the evidence.

IMPORTANT: You are also given the current pipeline source code. Before claiming the pipeline's logic is the cause of the issue, carefully check whether the existing code already handles this case correctly (e.g., it already deduplicates, already drops nulls, etc.). If the code already handles it, the root cause is NOT a logic bug in the pipeline — it is more likely an upstream data quality issue, a missing logging/alerting gap, or a transparency problem. Say so explicitly in the root_cause field.

Here is the evidence:

Issue: {issue}
Severity: {severity}
Column involved: {column}
Total rows affected by this type of issue: {total_affected}
Affected row(s):
{rows}
{stats_section}
{code_section}

Based ONLY on this evidence, respond with a JSON object containing exactly these fields:
- "root_cause": a plain-English explanation of why this likely happened
- "confidence": a number from 0 to 1 as a numeric float (e.g. 0.85, not words/text), how certain you are given the evidence available
- "reasoning": a short explanation of what evidence supports this confidence level, and what's missing or uncertain

Respond with ONLY the JSON object, no other text before or after it."""


def diagnose(evidence):
    """Takes a structured evidence dict from collect_evidence() and asks an LLM
    to reason about the root cause. Returns the diagnosis dict and which backend answered."""

    finding = evidence['finding']

    rows_text = ""
    for row in evidence['affected_rows']:
        rows_text += f"  {row}\n"

    stats_section = ""
    if 'column_stats' in evidence:
        s = evidence['column_stats']
        stats_section = f"\nColumn stats from clean (non-flagged) rows: min={s['min']}, max={s['max']}, mean={s['mean']}, median={s['median']}"

    code_section = ""
    if evidence.get('current_pipeline_code'):
        code_section = f"\nCurrent pipeline source code:\n```python\n{evidence['current_pipeline_code']}```"

    prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(
        issue=finding['issue'],
        severity=finding['severity'],
        column=evidence['column'],
        total_affected=evidence['total_affected_in_dataset'],
        rows=rows_text.strip(),
        stats_section=stats_section,
        code_section=code_section
    )

    response_text, backend = inference(prompt)

    try:
        # Strip markdown code fences if the LLM wraps its response in them
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        diagnosis = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"ERROR: LLM response was not valid JSON. Raw response:\n{response_text}")
        diagnosis = {
            'root_cause': 'Could not parse LLM response',
            'confidence': 0,
            'reasoning': f'Raw response: {response_text}'
        }

    return diagnosis, backend
