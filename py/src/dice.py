# Dicerolling.
# Parser and evaluator for dice roll inputs.

import collections, re
from random import randint
from utils import escape

ProtoToken = collections.namedtuple("ProtoToken", ["type", "value"])

TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d*)?"),  # Integer or decimal number
    ("OP",       r"[dk][hl]|[+\-*/^d()]"),  # Operators
    ("END",      r"[;\n]"),        # Line end / break characters
    ("SKIP",     r"[ \t]+"),       # Skip over spaces and tabs
    ("MISMATCH", r"."),            # Any other character
]
TOKEN_PATTERN = re.compile('|'.join(f"(?P<{pair[0]}>{pair[1]})" for pair in TOKEN_SPEC))

# Cut input into tokens.
# Based on tokenizer sample from the python docs.
# https://docs.python.org/3.6/library/re.html#regular-expression-examples
def tokenize(intext):
    tokens = []
    for item in TOKEN_PATTERN.finditer(intext):
        kind = item.lastgroup # group name
        value = item.group()
        if kind == "NUMBER":
            if '.' in value:
                value = float(value)
            else:
                value = int(value)
        # pass OP, END
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise RuntimeError(f"Couldn't interpret `{value}` from: {intext}")
        
        tokens.append(ProtoToken(kind, value))
    return tokens

# Convert tokens to symbol instances and divide them into individual rolls.
def symbolize(symbol_table, tokens):
    all_rolls = []
    current_roll = []
    for pretoken in tokens:
        symbol_id = pretoken.type
        if pretoken.type == "OP":
            symbol_id = pretoken.value
        try: # look up symbol type
            symbol = symbol_table[symbol_id]
        except KeyError:
            raise SyntaxError(f"Failed to find symbol type for token {pretoken}")

        token = symbol()
        if pretoken.type == "NUMBER":
            token.value = pretoken.value
        current_roll.append(token)

        if pretoken.type == "END":
            all_rolls.append(current_roll)
            current_roll = []

    if len(current_roll) > 0:
        if current_roll[-1]._kind != "END":
            current_roll.append(symbol_table["END"]())
        all_rolls.append(current_roll)
    return all_rolls

class DiceResult(collections.namedtuple("DiceResult", ["count", "size", "total", "rolls", "negative", "dropped"])):
    def full_detail(self):
        return f"[{self.base_roll()} = {self.negated()}{self.breakout()} = {str(self.total)}]"
    def breakout(self):
        drops_striked = [f"~~{self.rolls[i]}~~" if i in self.dropped else f"{self.rolls[i]}" for i in range(len(self.rolls))]
        return f"({'+'.join(drops_striked)})"
    def negated(self):
        return f"{'-' if self.negative else ''}"
    def base_roll(self):
        return f"{self.count}d{self.size}"
    def __repr__(self):
        return self.base_roll()

def force_integral(value, description=""):
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    else:
        raise ValueError(f"Expected integer # {description}: {value}")

def dice_roll(count, size):
    rolls = []
    negative = False

    count = force_integral(count, "dice count")
    if size < 0:
        raise ValueError(f"Negative dice don't exist (d{size})")
    size = force_integral(size, "dice size")

    if count < 0:
        count = -count
        negative = True

    if size == 0:
        for i in range(count):
            rolls.append(0)
    else:
        for i in range(count):
            rolls.append(randint(1, size))
    total = -sum(rolls) if negative else sum(rolls)
    return DiceResult(count, size, total, rolls, negative, [])

# Drop some dice from a roll and update its total.
# Defaults to dropping the `n` lowest dice.
# `high` option means dropping high dice.
# `keep` option means keeping `n` dice and dropping the rest.
def dice_drop(dice, n, high=False, keep=False):
    if not isinstance(dice, DiceResult):
        raise SyntaxError(f"Failed to drop dice (not a dice roll?)")
    n = force_integral(n, "dice to drop")
    if keep:
        n = dice.count - n
    if n < 0:
        raise ValueError(f"Can't drop negative dice ({n})")
    if n == 0:
        return DiceResult(dice.count, dice.size, dice.total, dice.rolls, dice.negative, [])

    sdice = sorted(list(enumerate(dice.rolls)), key=lambda x:x[1], reverse=high^keep)
    dropped = [x[0] for x in sdice[:n]]
    total = 0
    for i in range(len(dice.rolls)):
        if i not in dropped:
            total += dice.rolls[i]
    if dice.negative:
        total = -total

    return DiceResult(dice.count, dice.size, total, dice.rolls, dice.negative, dropped)

# Based on Pratt top-down operator precedence.
# http://effbot.org/zone/simple-top-down-parsing.htm
# Relies on a static symbol table for now; not thread-safe. haha python
class Evaluator:
    SYMBOL_TABLE = {}

    def __init__(self, tokens):
        self.token_iter = iter(tokens)
        self.token_current = None
        self._next()

    def _next(self):
        try:
            self.token_current = next(self.token_iter)
        except StopIteration as err:
            raise StopIteration(f"Expected further input. Missing operands?")
        return self.token_current

    def _current(self):
        return self.token_current

    def advance(self, expected=None):
        if expected and self._current()._kind != expected:
            raise SyntaxError(f"Missing expected: {expected}")
        return self._next()

    # Syntax tree base class
    class _Symbol:
        # token type
        _kind = None
        # literal value or computation result
        value = None
        # detailed info on operator computation such as dice resolution
        detail = None

        # parse tree links
        first = None
        second = None
        
        # operator binding power, 0 for literals.
        bp = 0

        # Null denotation: value for literals, prefix behavior for operators.
        def as_prefix(self, evaluator):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Left denotation: infix behavior for operators. Preceding expression
        # provided as `left`.
        def as_infix(self, evaluator, left):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Recursively describe the expression, showing detailed dice roll information
        def describe(self, breakout=False):
            if breakout and self._kind in ("d", "dl", "dh", "kl", "kh"):
                dice_breakout = self.detail.breakout()
                if self._kind == "d":
                    if self.detail.count < 2:
                        dice_breakout = ""
                    dice_count = "" if self.second == None else self.first.describe(breakout)
                    dice_size = self.first.describe(breakout) if self.second == None else self.second.describe(breakout)
                    return f"[{dice_count}d{dice_size} {dice_breakout}={self.value}]"
                else:
                    return f"[{self.first.describe()}{self._kind}{self.second.describe(breakout)} {dice_breakout}={self.value}]"
            if self._kind == "(": # parenthesis group
                return "(" + self.first.describe() + ")"
            if self.first != None and self.second != None: # infix
                return f"{self.first.describe(breakout)}{escape(self._kind)}{self.second.describe(breakout)}"
            if self.first != None: # prefix
                return f"{self._kind}{self.first.describe(breakout)}"
            else:
                return f"{self}"

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self.value}"
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))
            return "<" + " ".join(out) + ">"

    # Parse and evaluate an expression from symbols. Recursive.
    def expr(self, right_bp=0):
        # print(f"evaluating starting at {self.token_current}")
        prev = self._current()
        self._next()
        left = prev.as_prefix(self)
        while right_bp < self._current().bp:
            prev = self._current()
            self._next()
            left = prev.as_infix(self, left)
        return left

    @staticmethod
    def register_symbol(symbol_kind, bind_power=0):
        try:
            s = Evaluator.SYMBOL_TABLE[symbol_kind]
        except KeyError:
            class s(Evaluator._Symbol):
                pass
            s.__name__ = "symbol-" + symbol_kind
            s.__qualname__ = "symbol-" + symbol_kind
            s._kind = symbol_kind
            s.bp = bind_power
            # print(f"set bp of {s._kind} to {s.bp}")
            Evaluator.SYMBOL_TABLE[symbol_kind] = s
        else:
            s.bp = max(bind_power, s.bp)
        return s

    @staticmethod
    def register_prefix(kind, func, bind_power):
        def _as_prefix(self, evaluator):
            self.first = evaluator.expr(bind_power)
            self.second = None
            func(self, self.first)
            return self
        s = Evaluator.register_symbol(kind) # note we don't assign bp for prefix
        s.as_prefix = _as_prefix
        return s

    @staticmethod
    def register_infix(kind, func, bind_power, right_assoc=False):
        def _as_infix(self, evaluator, left):
            self.first = left
            self.second = evaluator.expr(bind_power - (1 if right_assoc else 0))
            func(self, self.first, self.second)
            return self
        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = _as_infix
        return s

    # Build parse tree(s) from symbols and compute results.
    # A break token results in several trees.
    def evaluate(self):
        ret = self.expr()
        if self._current()._kind != "END":
            raise SyntaxError("Parse error: missing operators?")
        return ret

def roll(intext):
    if len(intext) < 1:
        raise ValueError("Nothingness rolls eternal.")
    results = []
    pretokens = tokenize(intext)
    rolls = symbolize(Evaluator.SYMBOL_TABLE, pretokens)
    for roll in rolls:
        e = Evaluator(roll)
        results.append(e.evaluate())
    return results

def format_roll_results(results):
    out = ""
    for row in results:
        out += f"{row.describe(False)} => {row.value}  |  {row.describe(True)}"
        out += "\n"
    return out

def _dice_operator(node, x, y):
    node.detail = dice_roll(x.value, y.value)
    node.value = node.detail.total

def _dice_operator_prefix(node, x):
    node.detail = dice_roll(1, x.value)
    node.value = node.detail.total

def _dice_drop_low_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.value)
    node.value = node.detail.total

def _dice_drop_high_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.value, high=True)
    node.value = node.detail.total

def _dice_keep_low_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.value, high=False, keep=True)
    node.value = node.detail.total

def _dice_keep_high_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.value, high=True, keep=True)
    node.value = node.detail.total

def _add_operator(node, x, y):
    node.value = x.value+y.value

def _subtract_operator(node, x, y):
    node.value = x.value-y.value

def _negate_operator(node, x):
    node.value = -x.value

def _mult_operator(node, x, y):
    node.value = x.value*y.value

def _div_operator(node, x, y):
    node.value = x.value/y.value

def _pow_operator(node, x, y):
    node.value = x.value ** y.value

def _number_nud(self, ev):
    return self

def _left_paren_nud(self, ev):
    self.first = ev.expr()
    self.value = self.first.value
    ev.advance(expected=")")
    return self

# initialize symbol table with type classes
Evaluator.register_symbol("NUMBER").as_prefix = _number_nud
Evaluator.register_symbol("END")
Evaluator.register_symbol("(").as_prefix = _left_paren_nud
Evaluator.register_symbol(")")
Evaluator.register_infix("+", _add_operator, 10)
Evaluator.register_infix("-", _subtract_operator, 10)
Evaluator.register_infix("*", _mult_operator, 20)
Evaluator.register_infix("/", _div_operator, 20)
Evaluator.register_prefix("-", _negate_operator, 100)
Evaluator.register_infix("^", _pow_operator, 110, right_assoc=True)
Evaluator.register_infix("d", _dice_operator, 200)
Evaluator.register_prefix("d", _dice_operator_prefix, 200)
Evaluator.register_infix("dl", _dice_drop_low_operator, 190)
Evaluator.register_infix("dh", _dice_drop_high_operator, 190)
Evaluator.register_infix("kl", _dice_keep_low_operator, 190)
Evaluator.register_infix("kh", _dice_keep_high_operator, 190)

if __name__ == "__main__":
    while True:
        intext = input()
        try:
            results = roll(intext)
            print(format_roll_results(results))
        except (ArithmeticError, ValueError, RuntimeError, StopIteration, SyntaxError) as err:
            print(f"{err}")
