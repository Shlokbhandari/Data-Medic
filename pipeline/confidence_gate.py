CONFIDENCE_THRESHOLD = 0.7


def should_proceed(diagnosis):
    """Decides whether we're confident enough to attempt a patch, or should escalate to a human.
    Returns a dict with the decision and a plain-English reason."""

    confidence = diagnosis.get('confidence', 0)

    if confidence >= CONFIDENCE_THRESHOLD:
        return {
            'decision': 'proceed',
            'reason': f"Confidence {confidence} meets the {CONFIDENCE_THRESHOLD} threshold"
        }
    else:
        return {
            'decision': 'escalate',
            'reason': f"Confidence {confidence} is below the {CONFIDENCE_THRESHOLD} threshold, escalating to a human"
        }
