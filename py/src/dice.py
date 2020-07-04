# Dicerolling.
# Parser and evaluator for dice roll inputs.

import collections, itertools, operator, re
from functools import total_ordering
from math import factorial, sqrt
from random import randint
from utils import escape, codeblock

ProtoToken = collections.namedtuple("ProtoToken", ["type", "value"])

KEYWORDS = [
    "C", "choose", "repeat", "sqrt", "fact",
]
KEYWORD_PATTERN = '|'.join(KEYWORDS)
TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d*)?"),    # Integer or decimal number
    ("KEYWORD",  KEYWORD_PATTERN),   # Keywords
    ("DICE",     r"[dk][hl]|[d]"),   # Diceroll operators
    ("OP",       r"[+\-*×/÷%^()!]"), # Generic operators
    ("SEP",      r"[,]"),            # Separators like commas
    ("END",      r"[;\n]"),          # Line end / break characters
    ("SKIP",     r"[ \t]+"),         # Skip over spaces and tabs
    ("MISMATCH", r"."),              # Any other character
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
        if pretoken.type in ("OP", "DICE", "KEYWORD", "SEP"):
            symbol_id = pretoken.value
        try: # look up symbol type
            symbol = symbol_table[symbol_id]
        except KeyError:
            raise SyntaxError(
                f"Failed to find symbol type for {pretoken}")

        token = symbol()
        if pretoken.type == "NUMBER":
            token._value = pretoken.value
        current_roll.append(token)

        if pretoken.type == "END":
            all_rolls.append(current_roll)
            current_roll = []

    if len(current_roll) > 0:
        if current_roll[-1]._kind != "END":
            current_roll.append(symbol_table["END"]())
        all_rolls.append(current_roll)
    return all_rolls

def force_integral(value, description=""):
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    else:
        raise ValueError(f"Expected integer # {description}: {value}")

def single_roll(size):
    if size == 0:
        return 0
    else:
        return randint(1, size)

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

    for i in range(count):
        rolls.append(single_roll(size))

    return DiceValues(size, negative, items=rolls)

# Drop the highest or lowest value items from a collection.
# Defaults to dropping the `n` lowest items.
# `high` option means dropping high items.
# `keep` option means keeping `n` items and dropping the rest.
def dice_drop(dice, n, high=False, keep=False):
    if not isinstance(dice, CollectedValues):
        raise SyntaxError(f"Can't drop/keep (operand not a collection)")
    n = force_integral(n, "items to drop")
    if keep:
        if n < 0:
            raise ValueError(f"Can't keep negative # of items ({n})")
        # if keeping dice, we're dropping a complementary dice.
        # if we've already dropped more than that, we don't need to drop more.
        n = dice.get_remaining_count() - n
        if n < 0: # allow keeping more dice than are rolled (drop none)
            n = 0
    if n < 0:
        raise ValueError(f"Can't drop negative # of items ({n})")

    new_values = dice.copy()
    if n == 0:
        # nothing to drop
        return new_values

    # sort and pair with indices
    sdice = sorted(list(enumerate(dice.get_all_items())),
                    key=lambda x:x[1],
                    reverse=high^keep)
    # remove already dropped
    sdice = list(filter(lambda x: x[0] not in dice.dropped, sdice))
    # find n more to drop
    new_drops = [x[0] for x in sdice[:n]]
    
    new_values.dropped.extend(new_drops)
    return new_values

def dice_explode(dice, condition=None, max_explosion=1000):
    if not isinstance(dice, DiceValues):
        raise SyntaxError(f"Can't explode (not dice)")
    if condition == None:
        condition = lambda x: (x >= dice.dice_size)

    new_values = dice.copy()
    rolls = new_values.get_all_items()

    exploded = []
    exploded_indices = []
    for i in range(len(rolls)):
        if i in dice.dropped:
            continue
        if condition(rolls[i]) and len(exploded) < max_explosion:
            exploded_indices.append(len(rolls) + len(exploded))
            exploded.append(single_roll(dice.dice_size))

    i = 0
    while i < len(exploded) and len(exploded) < max_explosion:
        if condition(exploded[i]):
            exploded_indices.append(len(rolls) + len(exploded))
            exploded.append(single_roll(dice.dice_size))
        i += 1

    new_values.items.extend(exploded)
    new_values.added.extend(exploded_indices)
    return new_values 

# The result of evaluating an expression, to be stored in a parse tree node
# which required computation or collection. This is for operations with
# complexity that cannot be represented by formatting just the operator and
# operands.
class ExprResult:
    # repr will be how this expression's final result will be shown
    def __repr__(self):
        return f"{self.get_value()}"

    # Helpers allowing literal values and ExprResult instances to be handled
    # by a single code path
    @staticmethod
    def value(item):
        if isinstance(item, ExprResult):
            return item.get_value()
        return item
    @staticmethod
    def description(item):
        if isinstance(item, ExprResult):
            return item.get_description()
        return f"{item}"
    @staticmethod
    def unevaluated(item):
        if isinstance(item, ExprResult):
            return item.get_unevaluated()
        return f"{item}"

    # Numerical value for this expression.
    def get_value(self):
        raise NotImplementedError("Value missing for this expression.")

    # String description of how this expression was evaluated.
    def get_description(self):
        raise NotImplementedError("Description missing for this expression.")

    # String representing the state of the expression before any evaluation was done.
    def get_unevaluated(self):
        raise NotImplementedError("Expression missing unevaluated state.")

# Represents an expression which resolved to a single value,
# storing only the final value and description strings.
@total_ordering
class FlatExpr(ExprResult):
    def __init__(self, value, description, unevaluated):
        self.value = value
        self.description = description
        self.unevaluated = unevaluated
    # Overrides.
    def get_value(self):
        return self.value
    def get_description(self):
        return self.description
    def get_unevaluated(self):
        return self.unevaluated
    def __eq__(self, other):
        return self.value == ExprResult.value(other)
    def __lt__(self, other):
        return self.value < ExprResult.value(other)

# For representing an expression which evaluated to a collection from which items
# could have been added to or dropped from.
# Items are expected to be repr'able, either a literal value or ExprResult
class CollectedValues(ExprResult):
    def __init__(self, items=None, dropped=None, added=None):
        super().__init__()
        # dropped and added are lists of item indices, not items themselves
        self.items = items if items else []
        self.dropped = dropped if dropped else []
        self.added = added if added else []

    def __repr__(self):
        return f"[{len(self.items)} results]"

    def copy(self):
        return CollectedValues(self.items.copy(),
                               self.dropped.copy(),
                               self.added.copy())

    # Override. Default to returning the sum of non-dropped items.
    def get_value(self):
        return self.total()

    def format_item(self, base, index):
        if index in self.dropped:
            base = f"~~{base}~~"
        if index in self.added:
            base = f"_{base}_"
        return base

    # Override.
    def get_description(self, joiner=", "):
        out = joiner.join(
            [self.format_item(ExprResult.description(self.items[i]), i)
                for i in range(len(self.items))])
        return out

    # Override.
    def get_unevaluated(self, joiner=", "):
        out = joiner.join(
            [self.format_item(ExprResult.unevaluated(self.items[i]), i)
                for i in range(len(self.items))])
        return out

    # Returns all items, including dropped ones.
    def get_all_items(self):
        return self.items

    # Exclude dropped items.
    def get_remaining(self):
        remaining = []
        for i in range(len(self.items)):
            if i not in self.dropped:
                remaining.append(self.items[i])
        return remaining

    def get_remaining_count(self):
        return len(self.items) - len(self.dropped)

    # Aggregate together non-dropped items.
    def aggregate(self, func=None):
        values = self.get_remaining()
        return list(itertools.accumulate(values, func))

    def total(self, func=None):
        if self.get_remaining_count() < 1:
            return 0
        return self.aggregate(func)[-1]

# Represents several expressions' results collected together by one operator,
# such as `repeat()`.
class MultiExpr(CollectedValues):
    def __init__(self, contents=None, copy_source=None):
        if copy_source != None:
            super().__init__(
                items=copy_source.items.copy(),
                dropped=copy_source.dropped.copy(),
                added=copy_source.added.copy())
        else:
            super().__init__(items=contents)

    def __repr__(self):
        return f"{self.get_remaining_count()} result(s)"

    def copy(self):
        return MultiExpr(copy_source=self)

    def get_value(self):
        if self.get_remaining_count() == 1:
            return self.get_remaining()[0].get_value()
        return str(self)

    def get_description(self, joiner="\n"):
        out = "[\n"
        out += joiner.join(
            [self.format_item(f"**{ExprResult.value(self.items[i])}**  |  {ExprResult.description(self.items[i])}", i)
                for i in range(len(self.items))])
        return out + "\n]"

    def get_unevaluated(self):
        if len(self.get_all_items()) < 0:
            return "[empty MultiExpr]"

        all_identical = True
        first = self.items[0]
        for other in self.items[1:]:
            if ExprResult.unevaluated(first) != ExprResult.unevaluated(other):
                all_identical = False
                break

        if all_identical:
            return f"[{len(self.get_all_items())} repeats of: {ExprResult.unevaluated(first)}]"

        out = "["
        for item in self.items:
            out += f"{ExprResult.unevaluated(item)}, "
        out = out[:-2]
        out += "]"
        return out

class DiceValues(CollectedValues):
    def __init__(self, dice_size, negated=False,
                 items=None, dropped=None, added=None):
        super().__init__(items, dropped, added)
        self.dice_size = dice_size
        self.negated = negated

    def copy(self):
        return DiceValues(self.dice_size, self.negated, 
                          self.items.copy(),
                          self.dropped.copy(),
                          self.added.copy())

    def get_value(self):
        return super().get_value() * (-1 if self.negated else 1)

    # Override for joiner.
    def get_description(self):
        return "(" + super().get_description(joiner="+") + ")=" + str(self.get_value())

    # Override to hide rolls.
    def get_unevaluated(self):
        return ""

    def get_dice_size(self):
        return self.dice_size

    def get_base_roll_description(self):
        return f"{self.get_remaining_count()-len(self.added)}d{self.get_dice_size()}"

class SuccessValues(DiceValues):
    def __init__(self, dice_)

# Based on Pratt top-down operator precedence.
# http://effbot.org/zone/simple-top-down-parsing.htm
# Relies on a static symbol table for now; not thread-safe. haha python
class Evaluator:
    SYMBOL_TABLE = {}

    def __init__(self, tokens):
        self.token_list = tokens
        self.iter_pos = -1
        self.token_current = None
        self._next()

    def _jump_to(self, token_pos):
        try:
            self.token_current = self.token_list[token_pos]
            self.iter_pos = token_pos
        except IndexError as err:
            raise IndexError(
                f"Can't iterate from token position {token_pos}") from err
        return self.token_current

    def _next(self):
        try:
            self.token_current = self.token_list[self.iter_pos + 1]
            self.iter_pos += 1
        except (StopIteration, IndexError) as err:
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
            # numerical literal or resolved computation value
            self._value = None
            # detailed info on operator computation such as dice resolution
            self.detail = None

            # parse tree links
            self.first = None
            self.second = None

        def get_value(self):
            if self._value != None:
                return self._value
            if self.detail != None:
                return ExprResult.value(self.detail)
            return None

        # Null denotation: value for literals, prefix behavior for operators.
        def as_prefix(self, evaluator):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Left denotation: infix behavior for operators. Preceding expression
        # provided as `left`.
        def as_infix(self, evaluator, left):
            raise SyntaxError(f"Unexpected symbol: {self}")

        # Recursively describe this expression, showing dice breakouts and any
        # intermediate operations including random choice.
        # With uneval=True, describe as it was interpreted but not evaluated.
        # This should resemble the original input, but with whitespace removed
        # and possible parentheses inserted for clarity.
        def describe(self, uneval=False, predrop=False):
            describe_first = self.first.describe(uneval=uneval,
                predrop=self.is_dropkeepadd())\
                    if self.first != None else ""
            describe_second = self.second.describe(uneval=uneval)\
                    if self.second != None else ""

            if self._kind == "(": # parenthesis group
                inner = describe_first
                # skip showing parens if child is already parenthesized
                if inner[len(inner)-1] != ")" and inner[0] != "(":
                    inner = "(" + inner + ")"
                return inner

            spacer = " " if self._spaces else ""
            detail_description = ""
            
            if not uneval:
                if (not self.is_collection()) and (not self.contains_diceroll()):
                    # No child contains diceroll randomness, so just show the value
                    return f"{self.get_value()}"
                
                if self._kind == "repeat" and (not predrop): # repeated expression
                    return ExprResult.description(self.detail)

                if self.detail:
                    detail_description = " " + ExprResult.description(self.detail) if self.detail else ""
                if self.is_diceroll():
                    # hide details if parent drop/keep node already will show them
                    if len(self.detail.get_all_items()) < 2:
                        detail_description = "=" + str(self.detail.get_value())
                    if predrop:
                        detail_description = ""

            if self._function_like:
                close_function = ")"
                if len(describe_second) > 0:
                    close_function = f",{spacer}{describe_second})"
                return f"{self._kind}({describe_first}" + close_function

            left = describe_first
            right = describe_second
            if self.second == None:
                # No operands, just describe this node's value.
                if self.first == None:
                    return str(self)
                if self._postfix:
                    right = ""
                else:
                    left = ""
                    right = describe_first

            op = self._kind
            if not uneval:
                op = escape(self._kind)

            prewrap = f"{left}"+\
                    f"{spacer}{op}{spacer}"+\
                    f"{right}{detail_description}"

            if self._kind == "choose" or self._kind == "C":
                return "(" + prewrap + ")"
            elif self.is_diceroll() and not (predrop or uneval):
                return "[" + prewrap + "]"
            return prewrap

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self._value}"
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))
            return "<" + " ".join(out) + ">"

        def is_collection(self):
            return self.is_diceroll() or self._kind == "repeat"

        def is_diceroll(self):
            return self._kind == "d" or self.is_dropkeepadd()

        def is_dropkeepadd(self):
            return self._kind in ("dl", "dh", "kl", "kh", "!")

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

    @staticmethod
    def register_function_single(kind, func):
        # One-arg function.
        # basically a prefix operator, but requires parentheses like a
        # function call
        def _as_function(self, evaluator):
            evaluator.advance("(")
            self.first = evaluator.expr()
            self.second = None
            evaluator.advance(")")
            func(self, self.first)
            return self
        s = Evaluator.register_symbol(kind)
        s.as_prefix = _as_function
        s._function_like = True
        return s

    @staticmethod
    def register_function_double(kind, func):
        # Two-arg function.
        def _as_function(self, evaluator):
            evaluator.advance("(")
            self.first = evaluator.expr()
            evaluator.advance(",")
            self.second = evaluator.expr()
            evaluator.advance(")")
            func(self, self.first, self.second, evaluator)
            return self
        s = Evaluator.register_symbol(kind)
        s.as_prefix = _as_function
        s._function_like = True
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
        final_value = row.get_value()
        if final_value == None and row.detail != None:
            final_value = str(row.detail)
        out += codeblock(row.describe(uneval=True))+\
                f"=> **{final_value}**"+\
                f"  |  {row.describe()}"
        out += "\n"
    return out

def _dice_operator(node, x, y):
    node.detail = dice_roll(x.get_value(), y.get_value())

def _dice_operator_prefix(node, x):
    node.detail = dice_roll(1, x.get_value())

def _drop_low_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.get_value())

def _drop_high_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.get_value(), high=True)

def _keep_low_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.get_value(), high=False, keep=True)

def _keep_high_operator(node, x, y):
    node.detail = dice_drop(x.detail, y.get_value(), high=True, keep=True)

def _add_operator(node, x, y):
    node._value = x.get_value()+y.get_value()

def _subtract_operator(node, x, y):
    node._value = x.get_value()-y.get_value()

def _negate_operator(node, x):
    node._value = -x.get_value()

def _mult_operator(node, x, y):
    node._value = x.get_value()*y.get_value()

def _div_operator(node, x, y):
    node._value = x.get_value()/y.get_value()

def _pow_operator(node, x, y):
    node._value = x.get_value() ** y.get_value()

def _factorial_operator(node, x):
    node._value = factorial(x.get_value())

def _dice_explode_operator(node, x):
    node.detail = dice_explode(x.detail)

def _choose_operator(node, x, y):
    n = force_integral(x.get_value(), "choice operand")
    k = force_integral(y.get_value(), "choice operand")
    if n < 0 or k < 0:
        raise ValueError("choose operator must have positive operands")
    if k > n:
        node._value = 0
    else:
        node._value = factorial(n) / (factorial(k) * factorial(n - k))
        if node._value.is_integer():
            node._value = int(node._value)

def _sqrt_operator(node, x):
    node._value = sqrt(x.get_value())

def _remainder_operator(node, x, y):
    node._value = x.get_value() % y.get_value()

def _repeat_function(node, x, y, ev):
    exit_iter_pos = ev.iter_pos
    
    reps = force_integral(y.get_value(), "repetitions")
    if reps < 0:
        raise ValueError("Cannot repeat negative times")
    if reps == 0:
        node.detail = MultiExpr()
        return

    flats = [FlatExpr(x.get_value(),
                    x.describe(),
                    x.describe(uneval=True))]
    redo_node = x
    for i in range(reps - 1):
        ev._jump_to(ev.token_list.index(node)+2) # skip function open paren
        redo_node = ev.expr()
        flats.append(FlatExpr(redo_node.get_value(),
                            redo_node.describe(),
                            redo_node.describe(uneval=True)))
    # jump forward past end of function parentheses
    ev._jump_to(exit_iter_pos)

    node.detail = MultiExpr(contents=flats)

def _number_nud(self, ev):
    return self

def _left_paren_nud(self, ev):
    self.first = ev.expr()
    self._value = self.first.get_value()
    self.detail = self.first.detail
    ev.advance(expected=")")
    return self

# initialize symbol table with type classes
Evaluator.register_symbol("NUMBER").as_prefix = _number_nud
Evaluator.register_symbol("END")
Evaluator.register_symbol("(").as_prefix = _left_paren_nud
Evaluator.register_symbol(")")
Evaluator.register_symbol(",")
Evaluator.register_function_double("repeat", _repeat_function)
Evaluator.register_function_single("sqrt", _sqrt_operator)
Evaluator.register_function_single("fact", _factorial_operator)

Evaluator.register_infix("+", _add_operator, 10)
Evaluator.register_infix("-", _subtract_operator, 10)
Evaluator.register_infix("*", _mult_operator, 20)
Evaluator.register_infix("×", _mult_operator, 20)
Evaluator.register_infix("/", _div_operator, 20)
Evaluator.register_infix("÷", _div_operator, 20)
Evaluator.register_infix("%", _remainder_operator, 20)
Evaluator.register_prefix("-", _negate_operator, 100)
Evaluator.register_infix("^", _pow_operator, 110, right_assoc=True)

Evaluator.register_infix("C", _choose_operator, 130)._spaces = True
Evaluator.register_infix("choose", _choose_operator, 130)._spaces = True
Evaluator.register_postfix("!", _dice_explode_operator, 140)

Evaluator.register_infix("dl", _drop_low_operator, 190)
Evaluator.register_infix("dh", _drop_high_operator, 190)
Evaluator.register_infix("kl", _keep_low_operator, 190)
Evaluator.register_infix("kh", _keep_high_operator, 190)

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
