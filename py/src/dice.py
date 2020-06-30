# Dicerolling.
# Parser and evaluator for dice roll inputs.

# TODOs:
# echo input along with output lines (XdY notation in repr instead of expanded result?)
# allow `d` without preceding number to mean 1dX
# drop/keep operators
# parens for grouping
# clean up tokenizer

import collections, re
from random import randint

ProtoToken = collections.namedtuple("ProtoToken", ["type", "value"])

TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d*)?"),  # Integer or decimal number
    ("OP",       r"[+\-*/dk]"),    # Operators
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
            raise RuntimeError(f"Couldn't interpret [{value}] from: {intext}")
        
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
            print(f"Failed to find symbol type for token {pretoken}")
            raise

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
            raise StopIteration(f"Expected additional input following: {self.token_current}")
        return self.token_current

    def _current(self):
        return self.token_current

    class _Symbol:
        # token type
        _kind = None
        # literal value or computation result
        value = None
        # detailed info on operator computation
        detail = None

        # parse tree links
        first = None
        second = None
        
        # operator binding power, 0 for literals.
        bp = 0

        # Null denotation: value for literals, prefix behavior for operators.
        def as_prefix(self, evaluator):
            raise SyntaxError(f"Can't evaluate as prefix: {self}")

        # Left denotation: infix behavior for operators. Preceding expression
        # provided as `left`.
        def as_infix(self, evaluator, left):
            raise SyntaxError(f"Can't evaluate as infix: {self}")

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self.value}"
            if self.detail != None:
                return f"{self.detail}"
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))
            return "(" + " ".join(out) + ")"            

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
        def as_prefix(self, evaluator):
            # print(f"using {kind} as prefix operator")
            self.first = evaluator.expr(right_bp=bind_power)
            self.second = None
            try:
                func(self, self.first)
            except ArithmeticError as err:
                raise
            return self
        s = Evaluator.register_symbol(kind) # note we don't assign bp for prefix
        s.as_prefix = as_prefix
        return s

    @staticmethod
    def register_infix(kind, func, bind_power):
        def as_infix(self, evaluator, left):
            # print(f"using {kind} as infix operator with left {left}")
            self.first = left
            self.second = evaluator.expr(right_bp=bind_power)
            try:
                func(self, self.first, self.second)
            except ArithmeticError as err:
                raise
            return self
        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = as_infix
        return s

    # Build parse tree(s) from symbols and compute results.
    # A break token results in several trees.
    def evaluate(self):
        return self.expr()

def roll(intext):
    if len(intext) < 1:
        raise Exception("Nothingness rolls eternal.")
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
        out += f"{row.detail} = {row.value}"
        out += "\n"
    return out

class DiceResult(collections.namedtuple("DiceResult", ["count", "size", "total", "details", "negative"])):
    def full_detail(self):
        return f"[{self.count}d{self.size} = {'-' if self.negative else ''}({'+'.join(map(str,self.details))}) = {str(self.total)}]"
    def __repr__(self):
        return f"{'-' if self.negative else ''}({'+'.join(map(str,self.details))})"

def dice_roll(count, size):
    rolls = []
    negative = False
    if not isinstance(count, int):
        if isinstance(count, float) and count.is_integer():
            count = int(count)
        else:
            raise ArithmeticError(f"Invalid number of dice: {count}")
    if size < 0:
        raise ArithmeticError(f"Invalid dice (negative): {size}")
    if not isinstance(size, int):
        if isinstance(size, float) and size.is_integer():
            size = int(size)
        else:
            raise ArithmeticError(f"Invalid dice size: {size}")
    if count < 0:
        count = -count
        negative = True
    for i in range(count):
        rolls.append(randint(1, size))
    total = -sum(rolls) if negative else sum(rolls)
    return DiceResult(count, size, total, rolls, negative)

def _dice_operator(node, x, y):
    node.detail = dice_roll(x.value, y.value)
    node.value = node.detail.total

def _add_operator(node, x, y):
    node.value = x.value+y.value
    node.detail = f"{x}+{y}"

def _subtract_operator(node, x, y):
    node.value = x.value-y.value
    node.detail = f"{x}-{y}"

def _negate_operator(node, x):
    node.value = -x.value
    node.detail = f"-{x}"

def _mult_operator(node, x, y):
    node.value = x.value*y.value
    node.detail = f"{x}*{y}"

def _div_operator(node, x, y):
    node.value = x.value/y.value
    node.detail = f"{x}/{y}"

def _number_nud(self, ev):
    self.detail = f"{self.value}"
    return self

# initialize symbol table with type classes
Evaluator.register_symbol("NUMBER").as_prefix = _number_nud
Evaluator.register_symbol("END")
Evaluator.register_infix("+", _add_operator, 10)
Evaluator.register_infix("-", _subtract_operator, 10)
Evaluator.register_infix("*", _mult_operator, 20)
Evaluator.register_infix("/", _div_operator, 20)
Evaluator.register_prefix("-", _negate_operator, 100)
Evaluator.register_infix("d", _dice_operator, 50)

if __name__ == "__main__":
    while True:
        intext = input()
        try:
            results = roll(intext)        
            for result in results:
                print(f"{result.value}: {result.detail}")
        except (ArithmeticError, RuntimeError, StopIteration, SyntaxError) as err:
            print(f"{err}")
