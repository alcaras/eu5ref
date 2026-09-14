"""PDX value blocks → a readable formula and an evaluable expression.

A Clausewitz "script value" is not an expression tree: it is an ordered list
of operations applied to an accumulator that starts at 0.

    value = {
        add = { value = 0.5 subtract = "estate_power(estate_type:crown_estate)" }
        divide = 2
        add = "estate_power(estate_type:crown_estate)"
        max = 0.5
        min = 0.3
    }

reads as: acc = 0; acc += (0.5 − crown); acc /= 2; acc += crown; acc = min(acc,
0.5); acc = max(acc, 0.3) — i.e. `clamp((0.5 + crown) / 2, 0.3, 0.5)`.

**`min` is the FLOOR and `max` is the CEILING.** They are bounds on the
result, not the arithmetic functions of the same name, and swapping them
silently inverts every clamped formula on the site. They are lowered here to
`atleast` / `atmost` so the mistake cannot be made downstream.

Two outputs per block, from one op list:
  formula  a readable infix string ("clamp((0.5 + Crown estate power) / 2, 0.3, 0.5)")
  ops      the same thing as JSON the browser can evaluate (see `evaluate`,
           which the disaster page's exit-target calculator mirrors in JS)

Honest fallback, as everywhere: an operand or operator we cannot lower is
kept verbatim as a `['?', <script text>]` operand and the whole value is
flagged `unresolved`, rather than quietly producing a wrong number.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ref

# PDX op → our op. `value` sets the accumulator; the rest fold into it.
_OPS = {
    'value': 'set', 'add': 'add', 'subtract': 'sub',
    'multiply': 'mul', 'divide': 'div',
    'min': 'atleast',     # a FLOOR: acc = max(acc, x)
    'max': 'atmost',      # a CEILING: acc = min(acc, x)
}
# operators with no operand (`ceiling = yes`)
_ROUND = {'floor': 'floor', 'ceiling': 'ceil', 'round': 'round'}
# block keys that carry no arithmetic
_IGNORE = {'desc', 'format', 'fixed_point'}

# `"estate_power(estate_type:crown_estate)"` — a scope call used as a number.
_CALL = re.compile(r'^([a-z_]+)\(([a-z_]+):([a-z_0-9]+)\)$')
# `societal_value:aristocracy_vs_plutocracy`, `var:target_crown_power_variable`
_QUALIFIED = re.compile(r'^([a-z_]+):([a-z_0-9.]+)$')
# the game's own naming for a snapshotted goal
_TARGET_VAR = re.compile(r'^(?:target_)?(.+?)(?:_target)?(?:_variable|_var)?$')

# How a `<base>(<type>:<subject>)` call reads once the subject is named.
_CALL_PHRASE = {
    'estate_power': '{s} power',
    'estate_satisfaction': '{s} satisfaction',
    'estate': '{s}',
}
_QUALIFIED_PHRASE = {
    'societal_value': '{s}',
    'estate_satisfaction': '{s} satisfaction',
    'estate_power': '{s} power',
    'produced_in_country': '{s} produced',
    'modifier': '{s}',
    'tolerance': '{s} tolerance',
}


def subject_label(token: str) -> str:
    """`estate_type:crown_estate` / `crown_estate` → the game's display name."""
    key = str(token).strip().strip('"')
    if ':' in key:
        key = key.split(':', 1)[1]
    return ref.label_map().get(key) or ref.pretty(key)


def var_label(name: str) -> str:
    """A country variable's name → what it is.

    The files name every snapshotted goal `target_<what>_variable`, so that
    shape reads back as "the <what> target"; anything else keeps its own
    name, prettified."""
    raw = str(name).strip()
    if raw.startswith('var:'):
        raw = raw[4:]
    for suffix in ('_variable', '_var'):
        if raw.endswith(suffix):
            raw = raw[:-len(suffix)]
            break
    if raw.startswith('target_'):
        return f'the {raw[len("target_"):].replace("_", " ")} target'
    if raw.endswith('_target'):
        return f'the {raw[:-len("_target")].replace("_", " ")} target'
    return f'the {raw.replace("_", " ")}'


_SCOPE_PREFIX = re.compile(r'^(?:root|prev|this|from|scope:[a-z_]+|c:[A-Z]{2,4})\.')


def label_for(key: str) -> str:
    """A script token used as a number → a readable name for it."""
    k = _SCOPE_PREFIX.sub('', str(key).strip().strip('"'))
    if '.' in k and not _QUALIFIED.match(k):
        # a dotted read (`ruler.total_abilities`) — the last hop is the number
        k = k.rsplit('.', 1)[-1]
    m = _CALL.match(k)
    if m:
        base, _, subj = m.groups()
        phrase = _CALL_PHRASE.get(base, base.replace('_', ' ') + ' of {s}')
        return phrase.format(s=subject_label(subj))
    m = _QUALIFIED.match(k)
    if m:
        base, subj = m.groups()
        if base == 'var':
            return var_label(subj)
        if base == 'scope':
            return ref.pretty(subj)
        phrase = _QUALIFIED_PHRASE.get(base)
        if phrase:
            return phrase.format(s=subject_label(subj))
        return f'{base.replace("_", " ")} {subject_label(subj)}'
    return ref.pretty(k)


# ── lowering ────────────────────────────────────────────────────────────

def _number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _operand(v, depth: int):
    """One right-hand side → an operand node."""
    if hasattr(v, 'iterate_with_duplicates'):
        inner = _ops(v, depth + 1)
        return ['e', inner]
    n = _number(v)
    if n is not None:
        return ['n', n]
    s = str(v).strip().strip('"')
    # a named constant the game defines elsewhere (`monthly_spawn_chance_low`,
    # `estate_satisfaction_mild_bonus`) resolves to its own number
    c = constant(s)
    if c is not None:
        return ['n', c, s]
    if s.replace('.', '', 1).lstrip('-').isdigit():
        return ['n', float(s)]
    return ['v', s]


def _ops(tree, depth: int = 0) -> list:
    """A value block → [[op, operand?], …]."""
    out = []
    if depth > 6:
        return [['?', str(tree)]]
    try:
        pairs = list(tree.iterate_with_duplicates())
    except AttributeError:
        return [['add', _operand(tree, depth)]]
    for k, v in pairs:
        key = str(k)
        if key in _IGNORE:
            continue
        if key in _ROUND:
            out.append([_ROUND[key]])
            continue
        op = _OPS.get(key)
        if op is None:
            # `if = { limit = … add = … }` and anything else we do not model:
            # kept verbatim so the page can say so instead of guessing.
            out.append(['?', key])
            continue
        out.append([op, _operand(v, depth)])
    return out


def _inputs(ops: list, seen: dict) -> None:
    for op in ops:
        if len(op) < 2:
            continue
        operand = op[1]
        if operand[0] == 'v':
            seen.setdefault(operand[1], label_for(operand[1]))
        elif operand[0] == 'e':
            _inputs(operand[1], seen)


def _unresolved(ops: list) -> bool:
    for op in ops:
        if op[0] == '?':
            return True
        if len(op) > 1 and op[1][0] == '?':
            return True
        if len(op) > 1 and op[1][0] == 'e' and _unresolved(op[1][1]):
            return True
    return False


# ── rendering ───────────────────────────────────────────────────────────

_PREC = {'set': 0, 'add': 2, 'sub': 2, 'mul': 1, 'div': 1}
_SIGN = {'add': '+', 'sub': '−', 'mul': '×', 'div': '/'}


def _loose(text: str) -> bool:
    """Does this rendered formula have a bare operator at its top level?
    `clamp(a, b, c)` does not and never needs wrapping; `a + b` does."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch in '+−×/' and i and text[i - 1] == ' ':
            return True
    return False


def _operand_str(operand) -> str:
    kind = operand[0]
    if kind == 'n':
        return _num(operand[1])
    if kind == 'v':
        return label_for(operand[1])
    if kind == 'e':
        return _formula(operand[1], top=False)
    return f'[{operand[1]}]'


def _num(x: float) -> str:
    s = f'{x:g}'
    return s


def _formula(ops: list, top: bool = True) -> str:
    s, prec = None, 0
    i = 0
    while i < len(ops):
        op = ops[i]
        name = op[0]
        # a floor and a ceiling in a row is the game's way of writing a clamp
        if name in ('atleast', 'atmost') and i + 1 < len(ops) \
                and ops[i + 1][0] in ('atleast', 'atmost') and ops[i + 1][0] != name \
                and s is not None:
            lo = op[1] if name == 'atleast' else ops[i + 1][1]
            hi = ops[i + 1][1] if name == 'atleast' else op[1]
            s = f'clamp({s}, {_operand_str(lo)}, {_operand_str(hi)})'
            prec, i = 0, i + 2
            continue
        if name == '?':
            note = 'conditionally adjusted' if op[1] in ('if', 'else', 'else_if') \
                else f'adjusted by {op[1].replace("_", " ")}'
            s = f'{s} ({note})' if s else f'({note})'
            prec = 0
            i += 1
            continue
        if name in ('floor', 'ceil', 'round'):
            s = f'{name}({s if s is not None else "0"})'
            prec = 0
            i += 1
            continue
        t = _operand_str(op[1])
        tprec = 2 if op[1][0] == 'e' and _loose(t) else 0
        if name in ('atleast', 'atmost'):
            fn = 'max' if name == 'atleast' else 'min'
            s = f'{fn}({s if s is not None else "0"}, {t})'
            prec = 0
        elif s is None:
            if name in ('set', 'add'):
                # already parenthesized, so it is an atom from here on
                s, prec = (f'({t})' if tprec else t), 0
            elif name == 'sub':
                s, prec = f'−{t}', 0
            else:
                s, prec = f'0 {_SIGN[name]} {t}', _PREC[name]
        else:
            mine = _PREC[name]
            left = f'({s})' if mine < prec else s
            right = f'({t})' if tprec and tprec >= mine else t
            s, prec = f'{left} {_SIGN[name]} {right}', mine
        i += 1
    return s if s is not None else '0'


# ── evaluation (mirrored by the calculator in the browser) ──────────────

def evaluate(ops: list, env: dict) -> float | None:
    acc = 0.0
    for op in ops:
        name = op[0]
        if name == '?':
            return None
        if name == 'floor':
            acc = float(int(acc // 1))
            continue
        if name == 'ceil':
            acc = float(-int(-acc // 1))
            continue
        if name == 'round':
            acc = float(round(acc))
            continue
        operand = op[1]
        if operand[0] == 'n':
            x = operand[1]
        elif operand[0] == 'e':
            x = evaluate(operand[1], env)
        elif operand[0] == 'v':
            if operand[1] not in env:
                return None
            x = float(env[operand[1]])
        else:
            return None
        if x is None:
            return None
        if name == 'set':
            acc = x
        elif name == 'add':
            acc += x
        elif name == 'sub':
            acc -= x
        elif name == 'mul':
            acc *= x
        elif name == 'div':
            acc = acc / x if x else 0.0
        elif name == 'atleast':
            acc = max(acc, x)
        elif name == 'atmost':
            acc = min(acc, x)
        else:
            return None
    return acc


# ── named constants ─────────────────────────────────────────────────────

_CONSTS: dict[str, float] | None = None


def constant(name: str) -> float | None:
    """A script value that is just a number (`monthly_spawn_chance_low`)."""
    global _CONSTS
    if _CONSTS is None:
        _CONSTS = {}
        try:
            for k, sv in ref.parser.script_values.items():
                v = getattr(sv, 'direct_value', None)
                if v is None:
                    v = getattr(sv, 'value', None)
                    if v is not None and getattr(sv, 'calculations', None):
                        v = None
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    _CONSTS[k] = float(v)
        except Exception as exc:
            print(f'  script values unavailable: {exc}')
    return _CONSTS.get(str(name).strip())


# ── public entry point ──────────────────────────────────────────────────

COVERAGE = {'lowered': 0, 'unresolved': 0}


def lower(value) -> dict:
    """A `value = …` (block or scalar) → {ops, formula, inputs, unresolved}."""
    ops = _ops(value)
    seen: dict[str, str] = {}
    _inputs(ops, seen)
    bad = _unresolved(ops)
    COVERAGE['unresolved' if bad else 'lowered'] += 1
    out = {
        'ops': ops,
        'formula': _formula(ops),
        'inputs': [{'key': k, 'label': v} for k, v in seen.items()],
    }
    if bad:
        out['unresolved'] = True
    return out


# ── asserted checks ─────────────────────────────────────────────────────
# Worked numbers for the clamped targets, so a patch that changes a formula
# (or a refactor that swaps the floor and the ceiling) fails loudly instead
# of quietly publishing a wrong exit bar. Same idea as layout.py's CHECKS.
_CROWN = 'estate_power(estate_type:crown_estate)'
_NOBLES = 'estate_power(estate_type:nobles_estate)'
_BURGHERS = 'estate_power(estate_type:burghers_estate)'

CHECKS = [
    ('rise_of_the_szlachta', 'target_crown_power_variable', {_CROWN: 0.45}, 0.475),
    ('rise_of_the_szlachta', 'target_crown_power_variable', {_CROWN: 0.20}, 0.35),
    ('rise_of_the_szlachta', 'target_crown_power_variable', {_CROWN: 0.10}, 0.30),
    ('rise_of_the_szlachta', 'target_crown_power_variable', {_CROWN: 0.05}, 0.30),
    ('rise_of_the_szlachta', 'target_nobles_power_variable', {_NOBLES: 0.30}, 0.41),
    ('rise_of_the_szlachta', 'target_nobles_power_variable', {_NOBLES: 0.70}, 0.80),
    ('rise_of_the_szlachta', 'target_burghers_power_variable', {_BURGHERS: 0.02}, 0.10),
]


def set_variables(effect) -> dict[str, dict]:
    """An `on_start` effect → {variable name: lowered value}, for the
    variables it snapshots. Walks nested blocks (`if`/`else`) too."""
    out: dict[str, dict] = {}

    def walk(tree, depth=0):
        if depth > 5 or not hasattr(tree, 'iterate_with_duplicates'):
            return
        for k, v in tree.iterate_with_duplicates():
            key = str(k)
            if key == 'set_variable' and hasattr(v, 'iterate_with_duplicates'):
                name, val = None, None
                for k2, v2 in v.iterate_with_duplicates():
                    if str(k2) == 'name':
                        name = str(v2)
                    elif str(k2) == 'value':
                        val = v2
                if name and val is not None and name not in out:
                    out[name] = lower(val)
            elif hasattr(v, 'iterate_with_duplicates'):
                walk(v, depth + 1)

    walk(effect)
    return out


def run_checks() -> tuple[int, int]:
    ok = 0
    for key, var, env, expect in CHECKS:
        d = ref.parser.disasters.get(key)
        got = None
        if d is not None:
            lowered = set_variables(getattr(d, 'on_start', None)).get(var)
            if lowered:
                got = evaluate(lowered['ops'], env)
        inputs = ', '.join(f'{label_for(k)}={v}' for k, v in env.items())
        if got is not None and abs(got - expect) < 1e-9:
            ok += 1
        else:
            print(f'  CHECK FAILED {key}.{var} [{inputs}] → {got} (want {expect})')
    return ok, len(CHECKS)


def main() -> int:
    print('script value checks')
    for key in ('rise_of_the_szlachta', 'struggle_for_royal_power'):
        d = ref.parser.disasters[key]
        for name, lowered in set_variables(getattr(d, 'on_start', None)).items():
            print(f'  {key}.{name} = {lowered["formula"]}')
    ok, total = run_checks()
    print(f'  {ok}/{total} checks pass')
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
