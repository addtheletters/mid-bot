# Dicerolling.
# Parser and evaluator for dice roll inputs.

import collections, re
from math import factorial
from random import randint
from utils import escape, codeblock

ProtoToken = collections.namedtuple("ProtoToken", ["type", "value"])

KEYWORDS = [
    "C", "choose", "repeat", "sqrt",
]
KEYWORD_PATTERN = '|'.join(KEYWORDS)
TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d*)?"),  # Integer or decimal number
    ("KEYWORD",  KEYWORD_PATTERN), # Keywords
    ("DICE",     r"[dk][hl]|[d]"), # Diceroll operators
    ("OP",       r"[+\-*/^()!]"),  # Generic operators
    ("END",      r"[;\n]"),        # Line end / break characters
    ("SKIP",     r"[ \t]+"),       # Skip over spaces and tabs
    ("MISMATCH", r"."),            # Any other character
]
TOKEN_PATTERN = re.compile(
    '|'.join(f"(?P<{pair[0]}>{pair[1]})" for pair in TOKEN_SPEC))

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
            raise RuntimeError(f"Couldn't interpret <{value}> from: {intext}")
        
        tokens.append(ProtoToken(kind, value))
    return tokens

# Convert tokens to symbol instances and divide them into individual rolls.
def symbolize(symbol_table, tokens):
    all_rolls = []
    current_roll = []
    for pretoken in tokens:
        symbol_id = pretoken.type
        if pretoken.type in ("OP", "DICE", "KEYWORD"):
            symbol_id = pretoken.value
        try: # look up symbol type
            symbol = symbol_table[symbol_id]
        except KeyError:
            raise SyntaxError(
                f"Failed to find symbol type for {pretoken}")

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

class DiceResult(collections.namedtuple("DiceResult",
        ["count", "size", "total", "rolls", "negative", "dropped"])):
    def breakout(self):
        drops_striked = format_dropped(self.rolls, self.dropped)
        return f"({'+'.join(drops_striked)})"
    def negated(self):
        return f"{'-' if self.negative else ''}"
    def base_roll(self):
        return f"{self.count}d{self.size}"
    def __repr__(self):
        return self.base_roll()

def format_dropped(rolls, dropped):
    results = []
    for i in range(len(rolls)):
        if i in dropped:
            results.append(f"~~{rolls[i]}~~")
        else:
            results.append(f"{rolls[i]}")
    return results

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
        raise SyntaxError(f"Can't drop/keep (operand not a dice roll)")
    n = force_integral(n, "dice to drop")
    if keep:
        if n < 0:
            raise ValueError(f"Can't keep negative dice ({n})")
        # if keeping dice, we're dropping a complementary dice.
        # if we've already dropped more than that, we don't need to drop more.
        n = dice.count - len(dice.dropped) - n
        if n < 0: # allow keeping more dice than are rolled (drop none)
            n = 0
    if n < 0:
        raise ValueError(f"Can't drop negative dice ({n})")
    if n == 0:
        return DiceResult(
            dice.count, dice.size, dice.total, dice.rolls, dice.negative,
            dice.dropped)

    # sort and pair with indices
    sdice = sorted(list(enumerate(dice.rolls)),
                    key=lambda x:x[1],
                    reverse=high^keep)

    # remove already dropped
    sdice = list(filter(lambda x: x[0] not in dice.dropped, sdice))

    # drop n more dice
    new_drops = [x[0] for x in sdice[:n]]
    dropped = dice.dropped + new_drops
    total = 0
    for i in range(len(dice.rolls)):
        if i not in dropped:
            total += dice.rolls[i]
    if dice.negative:
        total = -total

    return DiceResult(
        dice.count, dice.size, total, dice.rolls, dice.negative, dropped)

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
            raise StopIteration(
                f"Expected further input. Missing operands?") from err
        return self.token_current

    def _current(self):
        return self.token_current

    def advance(self, expected=None):
        if expected and self._current()._kind != expected:
            raise SyntaxError(f"Missing expected: {expected}")
        return self._next()

    # Syntax tree base class
    class _Symbol:
        # token type. 
        _kind = None
        # operator binding power, 0 for literals.
        bp = 0

        # show operator after child for display purposes
        _postfix = False
        # add function-call parens when displaying operator with children
        _function_like = False
        # when displaying, insert spaces to separate operator from children
        _spaces = False

        def __init__(self):
            # literal value or computation result
            self.value = None
            # detailed info on operator computation such as dice resolution
            self.detail = None

            # parse tree links
            self.first = None
            self.second = None

        # Null denotation: value for literals, prefix behavior for operators.
        def as_prefix(self, evaluator):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Left denotation: infix behavior for operators. Preceding expression
        # provided as `left`.
        def as_infix(self, evaluator, left):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Recursively describe the expression, showing detailed dice roll
        # information
        # `breakout` means show the result of each dice rolled by
        #     the 'd' operator, and strikethrough dropped.
        # `predrop` helps format drop/keep operator, preventing the child
        #     'd' operator from showing its breakout.
        # `op_escape` when true will escape markdown around operator
        #     characters. Should be False when formatting for a code block.
        # `ex_ar` to expand intermediate arithmetic lacking dice rolls.
        def describe(self, breakout=False, op_escape=True,
                     ex_ar=False, predrop=False):
            if (not ex_ar) and (not self.contains_diceroll()):
                if self.value != None:
                    return f"{self.value}"

            describe_first = self.first.describe(breakout, op_escape, ex_ar)\
                if self.first != None else ""
            describe_second = self.second.describe(breakout, op_escape, ex_ar)\
                if self.second != None else ""

            if (not predrop) and breakout and self.is_diceroll():
                dice_breakout = " " + self.detail.breakout()
                if self._kind == "d":
                    if self.detail.count < 2:
                        dice_breakout = ""
                    dice_count = "" if self.second == None\
                                    else describe_first
                    dice_size = describe_first\
                                    if self.second == None\
                                    else describe_second
                    return f"[{dice_count}d{dice_size}"+\
                            f"{dice_breakout}={self.value}]"
                else:
                    return f"[{self.first.describe(breakout, op_escape, ex_ar, predrop=True)}"+\
                            f"{self._kind}{describe_second}"+\
                            f"{dice_breakout}={self.value}]"
            
            spacer = " " if self._spaces else ""

            if self._kind == "(": # parenthesis group
                inner = describe_first
                if inner[len(inner)-1] != ")":
                    inner = "(" + inner + ")"
                return inner

            if self._function_like:
                return f"{self._kind}({self.describe_first},{spacer}{self.describe_second})"

            if self.first != None and self.second != None: # infix
                op = self._kind
                if op_escape:
                    op = escape(op)
                ext_predrop = predrop if self.is_dropkeep() else False
                prewrap = f"{self.first.describe(breakout, op_escape, ex_ar, predrop=ext_predrop)}"+\
                        f"{spacer}{op}{spacer}"+\
                        f"{describe_second}"
                if self._kind == "choose" or self._kind == "C":
                    return "(" + prewrap + ")"
                return prewrap
            if self.first != None: # prefix or postfix, one child
                child_describe = describe_first
                if self._postfix:
                    return f"{child_describe}{spacer}{self._kind}"
                return f"{self._kind}{spacer}{child_describe}"
            else:
                return f"{self}"

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self.value}"
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))
            return "<" + " ".join(out) + ">"

        def is_diceroll(self):
            return self._kind == "d" or self.is_dropkeep()

        def is_dropkeep(self):
            return self._kind in ("dl", "dh", "kl", "kh")

        # Is this node dice, or does any node in this subtree have dice?
        def contains_diceroll(self):
            if self.is_diceroll():
                return True
            if self.first != None:
                has_dice = self.first.contains_diceroll()
                if self.second != None:
                    has_dice = has_dice or self.second.contains_diceroll()
                return has_dice
            return False

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
        s = Evaluator.register_symbol(kind) # don't assign to bp for prefix
        s.as_prefix = _as_prefix
        return s

    @staticmethod
    def register_infix(kind, func, bind_power, right_assoc=False):
        def _as_infix(self, evaluator, left):
            self.first = left
            self.second = evaluator.expr(
                bind_power - (1 if right_assoc else 0))
            func(self, self.first, self.second)
            return self
        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = _as_infix
        return s

    @staticmethod
    def register_postfix(kind, func, bind_power):
        # override as_infix so postfix operators are caught by lookahead
        # as infix operators that rely solely on existing left expression
        # and don't call expr
        def _as_postfix(self, evaluator, left):
            self.first = left
            self.second = None
            func(self, self.first)
            return self
        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = _as_postfix
        s._postfix = True
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
        out += codeblock(row.describe(breakout=False,
                                      op_escape=False,
                                      ex_ar=True))+\
                f"=> **{row.value}**"+\
                f"  |  {row.describe(breakout=True)}"
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

def _factorial_operator(node, x):
    node.value = factorial(x.value)

def _choose_operator(node, x, y):
    n = force_integral(x.value, "choice operand")
    k = force_integral(y.value, "choice operand")
    if n < 0 or k < 0:
        raise ValueError("choose operator must have positive operands")
    if k > n:
        node.value = 0
    else:
        node.value = factorial(n) / (factorial(k) * factorial(n - k))

def _number_nud(self, ev):
    return self

def _left_paren_nud(self, ev):
    self.first = ev.expr()
    self.value = self.first.value
    self.detail = self.first.detail
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

Evaluator.register_postfix("!", _factorial_operator, 120)

Evaluator.register_infix("C", _choose_operator, 130)
Evaluator.register_infix("choose", _choose_operator, 130)._spaces = True

Evaluator.register_infix("dl", _dice_drop_low_operator, 190)
Evaluator.register_infix("dh", _dice_drop_high_operator, 190)
Evaluator.register_infix("kl", _dice_keep_low_operator, 190)
Evaluator.register_infix("kh", _dice_keep_high_operator, 190)

Evaluator.register_infix("d", _dice_operator, 200)
Evaluator.register_prefix("d", _dice_operator_prefix, 200)

if __name__ == "__main__":
    while True:
        intext = input()
        try:
            results = roll(intext)
            print(format_roll_results(results))
        except (ArithmeticError, 
                ValueError, 
                RuntimeError, 
                StopIteration, 
                SyntaxError) as err:
            print(f"{err}")
