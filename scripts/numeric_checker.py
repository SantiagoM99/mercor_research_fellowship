"""Conservative parser for a restricted single-claim diagnostic, not full deliverables."""
from decimal import Decimal
import re

NUMBER = r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'


def check_numeric(response, bounds, unit):
    """Read one explicit 'is NUMBER UNIT' claim. Never receive the gold value/label."""
    if len(re.findall(r'\bis\s+', response, re.I)) != 1:
        return dict(verdict=None, reason='missing_or_multiple_claims')
    match = re.fullmatch(r'.*\bis\s+('+NUMBER+r')\s*(%|x|million dollars)?\s*\.?', response, re.I)
    if not match:
        return dict(verdict=None, reason='unsupported_or_ambiguous_expression')
    value, observed_unit = match.groups()
    if (observed_unit or '').lower() != unit:
        return dict(verdict=None, reason='missing_or_unsupported_unit')
    number = Decimal(value)
    lo, hi = map(Decimal, bounds)
    if not lo.is_finite() or not hi.is_finite() or lo > hi:
        raise ValueError('Invalid interval')
    return dict(verdict=int(lo <= number <= hi), value=str(number), unit=unit, reason='parsed_explicit_claim')
