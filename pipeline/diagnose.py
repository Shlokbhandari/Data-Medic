import json
from llm import inference


DIAGNOSIS_PROMPT_TEMPLATE = """You are a data pipeline diagnostician. You are given evidence about a data quality issue found in a pipeline. Your job is to determine why this issue likely happened, based ONLY on the evidence provided. Do not invent or assume anything not present in the evidence.

Here is the evidence:

Issue: {issue}
Severity: {severity}
Column involved: {column}
Total rows affected by this type of issue: {total_affected}
Affected row(s):
{rows}

Based ONLY on this evidence, respond with a JSON object containing exactly these fields:
- "root_cause": a plain-English explanation of why this likely happened
- "confidence": a number from 0 to 1, how certain you are given the evidence available
- "reasoning": a short explanation of what evidence supports this confidence level, and what's missing or uncertain

Respond with ONLY the JSON object, no other text before or after it."""


def diagnose(evidence):
    """Takes a structured evidence dict from collect_evidence() and asks an LLM
    to reason about the root cause. Returns the diagnosis dict and which backend answered."""

    finding = evidence['finding']

    rows_text = ""
    for row in evidence['affected_rows']:
        rows_text += f"  {row}\n"

    prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(
        issue=finding['issue'],
        severity=finding['severity'],
        column=evidence['column'],
        total_affected=evidence['total_affected_in_dataset'],
        rows=rows_text.strip()
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
