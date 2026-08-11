from patch import generate_patch
from sandbox import create_sandbox, run_in_sandbox, cleanup_sandbox
from validate import check_no_regression, check_issue_addressed


def generate_and_validate_with_retry(diagnosis, evidence, current_code, finding_type, max_attempts=3):
    """Attempts to generate a valid, passing patch with informed retries.

    Each failed attempt feeds its specific failure reason into the next attempt
    so the LLM can adjust. Returns the final result with full attempt history."""

    attempts = []

    for attempt_num in range(1, max_attempts + 1):
        # Build extra context from previous failures
        extra_context = ''
        if attempts:
            last = attempts[-1]
            extra_context = f"Attempt {len(attempts)} failed. Reason: {last['failure_reason']}"

        patch_result, backend = generate_patch(diagnosis, evidence, current_code, extra_context=extra_context)

        attempt = {
            'attempt': attempt_num,
            'backend': backend,
            'explanation': patch_result.get('explanation', ''),
            'syntax_valid': patch_result.get('syntax_valid', False),
            'syntax_error': patch_result.get('syntax_error'),
            'failure_reason': None,
            'regression_check': None,
            'issue_check': None,
        }

        if not patch_result.get('syntax_valid', False):
            attempt['failure_reason'] = f"Syntax error: {patch_result.get('syntax_error', 'unknown')}"
            attempts.append(attempt)
            continue

        # Syntax passed — run through sandbox validation
        baseline_patch = {'patched_code': current_code}
        baseline_sandbox = create_sandbox(baseline_patch, target_file='pipeline/run_pipeline.py')
        patched_sandbox = create_sandbox(patch_result, target_file='pipeline/run_pipeline.py')

        try:
            input_csv = 'data/orders_broken.csv'
            baseline_result = run_in_sandbox(baseline_sandbox['sandbox_path'], input_csv)
            patched_result = run_in_sandbox(patched_sandbox['sandbox_path'], input_csv)
        finally:
            cleanup_sandbox(baseline_sandbox['sandbox_path'])
            cleanup_sandbox(patched_sandbox['sandbox_path'])

        regression = check_no_regression(baseline_result, patched_result)
        issue = check_issue_addressed(finding_type, baseline_result, patched_result)

        attempt['regression_check'] = regression
        attempt['issue_check'] = issue

        if regression['passed'] and issue['passed']:
            attempts.append(attempt)
            return {
                'success': True,
                'patch': patch_result,
                'backend': backend,
                'attempts': attempts,
                'total_attempts': attempt_num,
            }

        # Build a specific failure reason for the next retry
        reasons = []
        if not regression['passed']:
            reasons.append(f"Regression check failed: {regression['explanation']}")
        if not issue['passed']:
            reasons.append(f"Issue check failed: {issue['explanation']}")
        attempt['failure_reason'] = '; '.join(reasons)
        attempts.append(attempt)

    return {
        'success': False,
        'patch': None,
        'backend': None,
        'attempts': attempts,
        'total_attempts': max_attempts,
        'escalation_reason': f"All {max_attempts} attempts failed. Escalating to a human.",
    }
