"""Execution oracle and metrics for the fixed, authored order diagnostic.

Only passes executes source, and its input must be caller-authored candidate
code. Judge response text is parsed as JSON and is never executed.
"""

import builtins
import copy
import json


def passes(code, task):
    """Check an authored candidate against every fixed execution case."""
    namespace = {}
    try:
        exec(compile(code, '<authored candidate>', 'exec'), namespace)
        solve = namespace.get('solve')
        if not callable(solve):
            return False
    except BaseException:
        return False

    for case in task['tests']:
        args = copy.deepcopy(case['args'])
        before = copy.deepcopy(args)
        expected_error = None
        if 'error' in case:
            expected_error = getattr(builtins, case['error'], None)
            if not (isinstance(expected_error, type)
                    and issubclass(expected_error, BaseException)):
                return False
        try:
            result = solve(*args)
        except BaseException as exc:
            if expected_error is None or not isinstance(exc, expected_error):
                return False
        else:
            if expected_error is not None:
                return False
            try:
                if result != case['expected']:
                    return False
            except BaseException:
                return False
        if task.get('preserve_inputs', False) and args != before:
            return False
    return True


def gold(case, tasks):
    """Return the binary-contract decision, including both kinds of tie."""
    task = tasks[case['task_id']]
    a, b = (passes(code, task) for code in case['options'])
    if a == b:
        return 'TIE'
    return 'A' if a else 'B'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-JSON constant')


def score(text, expected):
    """Parse without repair; return exactly the three preregistered fields."""
    invalid = dict(schema_valid=False, winner=None, correct=False)
    if not isinstance(text, str):
        return invalid
    try:
        value = json.loads(text, object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
    except (ValueError, TypeError, RecursionError):
        return invalid
    if not isinstance(value, dict) or set(value) != {'winner', 'reason'}:
        return invalid
    winner = value['winner']
    if (not isinstance(winner, str) or winner not in ('A', 'B', 'TIE')
            or not isinstance(value['reason'], str)):
        return invalid
    return dict(schema_valid=True, winner=winner, correct=winner == expected)


def summarize(records):
    """Aggregate one complete model block, rejecting malformed schedules."""
    records = list(records)
    if len(records) != 24:
        raise ValueError('Expected exactly 24 records')
    groups = {}
    seen = set()
    controls = {'both_valid': 0, 'both_buggy': 0}
    try:
        for record in records:
            case_id = record['case_id']
            task_id = record['task_id']
            if (not isinstance(case_id, str) or not case_id
                    or not isinstance(task_id, str) or not task_id
                    or case_id in seen):
                raise ValueError('Invalid or duplicate case identifier')
            seen.add(case_id)
            kind, order = record['kind'], record['order']
            if kind == 'main' and order in ('canonical', 'reversed'):
                cell = order
                expected = 'A' if order == 'canonical' else 'B'
            elif kind in controls and order == 'control':
                cell = 'control'
                controls[kind] += 1
                expected = 'TIE'
            else:
                raise ValueError('Unsupported kind or order')
            group = groups.setdefault(task_id, {})
            if cell in group:
                raise ValueError('Duplicate task cell')
            group[cell] = record
            scored = record['score']
            if (set(scored) != {'schema_valid', 'winner', 'correct'}
                    or type(scored['schema_valid']) is not bool
                    or type(scored['correct']) is not bool):
                raise ValueError('Malformed score')
            if scored['schema_valid']:
                if (scored['winner'] not in ('A', 'B', 'TIE')
                        or scored['correct'] != (scored['winner'] == expected)):
                    raise ValueError('Inconsistent score')
            elif scored['winner'] is not None or scored['correct']:
                raise ValueError('Malformed invalid score')
    except (KeyError, TypeError) as exc:
        raise ValueError('Malformed record') from exc
    if (len(groups) != 8 or controls != {'both_valid': 4, 'both_buggy': 4}
            or any(set(group) != {'canonical', 'reversed', 'control'}
                   for group in groups.values())):
        raise ValueError('Incomplete or malformed schedule')

    metrics = dict.fromkeys((
        'schema_valid', 'main_correct', 'correct_when_valid_first',
        'correct_when_valid_second', 'control_correct', 'both_valid',
        'both_buggy', 'consistent_pair', 'changed_pair', 'invalid_pair',
        'both_correct_pair', 'consistent_wrong_pair', 'persistent_tie_pair',
        'always_A_pair', 'always_B_pair'), 0)
    metrics.update(total_calls=24, main_calls=16, control_calls=8, pairs=8)
    for record in records:
        scored = record['score']
        metrics['schema_valid'] += int(scored['schema_valid'])
        correct = int(scored['correct'])
        if record['kind'] == 'main':
            metrics['main_correct'] += correct
            field = ('correct_when_valid_first' if record['order'] == 'canonical'
                     else 'correct_when_valid_second')
            metrics[field] += correct
        else:
            metrics['control_correct'] += correct
            metrics[record['kind']] += correct

    def normalize(scored, valid_label):
        if not scored['schema_valid']:
            return None
        if scored['winner'] == 'TIE':
            return 'tie'
        return 'valid' if scored['winner'] == valid_label else 'buggy'

    for group in groups.values():
        first = group['canonical']['score']
        second = group['reversed']['score']
        a, b = normalize(first, 'A'), normalize(second, 'B')
        if a is None or b is None:
            metrics['invalid_pair'] += 1
            continue
        metrics['consistent_pair' if a == b else 'changed_pair'] += 1
        metrics['both_correct_pair'] += int(a == b == 'valid')
        metrics['consistent_wrong_pair'] += int(a == b == 'buggy')
        metrics['persistent_tie_pair'] += int(a == b == 'tie')
        metrics['always_A_pair'] += int(first['winner'] == second['winner'] == 'A')
        metrics['always_B_pair'] += int(first['winner'] == second['winner'] == 'B')
    return metrics
