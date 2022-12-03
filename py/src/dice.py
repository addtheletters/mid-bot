# Dicerolling.
# Parser and evaluator for dice roll inputs.

import re
import typing
from math import factorial, sqrt

from dice_details import *
from utils import codeblock, escape

KEYWORDS = ["C", "choose", "repeat", "sqrt", "fact", "agg"]
KEYWORD_PATTERN = "|".join(KEYWORDS)
# fmt: off
TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d*)?"),               # Integer or decimal number
    ("KEYWORD",  KEYWORD_PATTERN),              # Keywords
    ("DICE",     r"[d]"),                       # Diceroll operators
    ("DIETYPE",  r"[cF]"),                      # Special types of dice usable with the diceroll operator
    ("SETOP",    r"~?\?|[kp]|[!x]o?|rr?"),      # Set operators
    ("SETSEL",   r"[hl]|even|odd"),             # Set selectors, not including comparisons
    ("COMP",     r"[><~]=|[><=]"),              # Comparisons, also usable as set selectors
    ("OP",       r"[+\-*×/÷%^(){}]"),           # Generic operators
    ("SEP",      r"[,]"),                       # Separators like commas
    ("END",      r"[;\n]"),                     # Line end / break characters
    ("SKIP",     r"[ \t]+"),                    # Skip over spaces and tabs
    ("MISMATCH", r"."),                         # Any other character
]
TOKEN_PATTERN = re.compile(
    '|'.join(f"(?P<{pair[0]}>{pair[1]})" for pair in TOKEN_SPEC))
# fmt: on

COMPARISONS = {
    "=": lambda x, y: x == y,
    ">": lambda x, y: x > y,
    "<": lambda x, y: x < y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "~=": lambda x, y: x != y,
}

ARITHMETICS = {
    "+": lambda x, y: x + y,
    "-": lambda x, y: x - y,
    "*": lambda x, y: x * y,
    "/": lambda x, y: x / y,
    "%": lambda x, y: x % y,
    "^": lambda x, y: x**y,
}


# Tokenizes a formula to symbol instances and divides them into individual rolls.
def symbolize(symbol_table, intext: str):
    all_rolls = []
    current_roll = []

    for item in TOKEN_PATTERN.finditer(intext):
        # Cut input into tokens.
        # https://docs.python.org/3.6/library/re.html#writing-a-tokenizer
        kind = item.lastgroup  # group name
        value = item.group()
        if kind == "NUMBER":
            if "." in value:
                value = float(value)
            else:
                value = int(value)
        # pass OP, END
        elif kind == "SKIP":
            continue
        elif kind == "MISMATCH":
            raise RuntimeError(f"Couldn't interpret <{value}> from: {intext}")

        # determine the symbol type
        symbol_id = kind
        if kind in ("OP", "DICE", "KEYWORD", "SEP", "COMP", "SETOP", "SETSEL"):
            symbol_id = value
        try:  # look up symbol type
            symbol = symbol_table[symbol_id]
        except KeyError:
            raise SyntaxError(f"Failed to find symbol type for {symbol_id}")

        # construct the symbol instance and populate its value if needed
        token = symbol()
        if kind == "NUMBER":
            token._value = value
        current_roll.append(token)

        # if reached an end token, wrap up the current roll
        if kind == "END":
            all_rolls.append(current_roll)
            current_roll = []

    # end the final roll if no explicit END token is found
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

    # Syntax tree base class
    class _Symbol:
        # token type.
        _kind = None
        # operator binding power, 0 for literals.
        _bp = 0

        # add function-call parens when displaying operator with children
        _function_like = False

        def __init__(self):
            # numerical literal or resolved computation value
            self._value = None
            # detailed info on operator computation such as dice resolution
            self.detail: ExprResult | None = None

            # parse tree links
            self.first: Evaluator._Symbol | None = None
            self.second: Evaluator._Symbol | None = None

        def get_value(self):
            if self._value != None:
                return self._value
            if self.detail != None:
                return ExprResult.value(self.detail)
            return None

        # Null denotation: value for literals, prefix behavior for operators.
        def as_prefix(self, evaluator):
            raise SyntaxError(f"Unexpected symbol (nud): {self}")

        # Left denotation: infix behavior for operators. Preceding expression
        # provided as `left`.
        def as_infix(self, evaluator, left):
            raise SyntaxError(f"Unexpected symbol (led): {self}")

        # when describing, show this node's operator after child
        def should_postfix(self) -> bool:
            return False

        # when describing, insert spaces to separate operator from children
        def should_spaces(self) -> bool:
            return False

        # Recursively describe this expression.
        # This should resemble the original input.
        # If `evaluated`, the description reduces nodes lacking dice operations
        # to their result value and shows the results of dicerolls.
        # If `top_level`, sets of expressions are allowed to join with newlines for
        # better readability.
        def describe(self, evaluated=False, top_level=False) -> str:
            if self.second == None and self.first == None:
                if self._kind in ARITHMETICS.keys():
                    # display lone symbol if used as operand such as in agg()
                    return f"{self._kind}"
                if self.detail:
                    return ExprResult.description(self.detail, evaluated, top_level)
                if self._kind != "NUMBER":
                    print(self._kind)
                return str(self)

            if evaluated:
                if not self.contains_diceroll():
                    if self.get_value() == None:
                        return escape(str(self))
                    return f"{self.get_value()}"
                if self.detail:
                    return ExprResult.description(self.detail, evaluated, top_level)

            describe_first = self.first.describe(evaluated) if self.first else ""
            describe_second = self.second.describe(evaluated) if self.second else ""
            spacer = " " if self.should_spaces() else ""

            if self._function_like:
                close_function = ")"
                if len(describe_second) > 0:
                    close_function = f",{spacer}{describe_second})"
                return f"{self._kind}({describe_first}" + close_function

            if self._kind == "(":  # parenthesis group
                return "(" + describe_first + ")"

            left = describe_first
            right = describe_second
            op = escape(self._kind)
            if self.second == None and not self.should_postfix():
                left = ""
                right = describe_first
            return f"{left}{spacer}{op}{spacer}{right}"

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self._value}"
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))  # type: ignore
            return "<" + " ".join(out) + ">"

        def final_repr(self):
            if self.detail != None:
                return str(self.detail)
            final_value = self.get_value()
            if final_value == None:
                return str(self)
            return str(final_value)

        def is_diceroll(self):
            return self._kind == "d" or self.is_set_operation()

        def is_set_operation(self):
            return self._kind in ("k", "p", "?", "~?", "!", "{", "repeat")

        def is_selector(self):
            return self._kind in (
                "=",
                "~=",
                ">",
                ">=",
                "<",
                "<=",
                "h",
                "l",
                "even",
                "odd",
            )

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
            raise IndexError(f"Can't iterate from token position {token_pos}") from err
        return self.token_current

    def _next(self):
        try:
            self.token_current = self.token_list[self.iter_pos + 1]
            self.iter_pos += 1
        except (StopIteration, IndexError) as err:
            raise StopIteration(f"Expected further input. Missing operands?") from err
        return self.token_current

    def _current(self):
        return self.token_current

    def peek(self) -> _Symbol | None:
        try:
            peeked = self.token_list[self.iter_pos]
        except IndexError:
            return None
        return peeked

    def advance(self, expected=None):
        if expected and self._current()._kind != expected:  # type: ignore
            raise SyntaxError(f"Missing expected: {expected}")
        return self._next()

    # Parse and evaluate an expression from symbols. Recursive.
    def expr(self, right_bp=0):
        prev = self._current()
        self._next()
        left = prev.as_prefix(self)  # type: ignore
        while right_bp < self._current()._bp:  # type: ignore
            prev = self._current()
            self._next()
            left = prev.as_infix(self, left)  # type: ignore
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
            s._bp = bind_power
            Evaluator.SYMBOL_TABLE[symbol_kind] = s
        else:
            s._bp = max(bind_power, s._bp)
        return s

    @staticmethod
    def register_prefix(kind, func, bind_power):
        def _as_prefix(self, evaluator):
            self.first = evaluator.expr(bind_power)
            self.second = None
            func(self, self.first)
            return self

        s = Evaluator.register_symbol(kind)  # don't assign to bp for prefix
        s.as_prefix = _as_prefix
        return s

    @staticmethod
    def register_infix(kind, func, bind_power, right_assoc=False, spaces=False):
        def _as_infix(self, evaluator, left):
            self.first = left
            self.second = evaluator.expr(bind_power - (1 if right_assoc else 0))
            func(self, self.first, self.second)
            return self

        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = _as_infix
        if spaces:
            s.should_spaces = lambda self: True
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
        s.should_postfix = lambda self: True
        return s

    @staticmethod
    def register_hybrid_infix_postfix(
        kind,
        func_infix: typing.Callable,
        func_postfix: typing.Callable,
        check_right_func: typing.Callable[..., bool],
        bind_power,
    ):
        def _as_hybrid(self, evaluator: Evaluator, left):
            self.first = left
            right = evaluator.peek()
            if check_right_func(right):
                self.second = evaluator.expr(bind_power)  # left-associative only
                func_infix(self, self.first, self.second)
            else:
                self.second = None
                func_postfix(self, self.first)
            return self

        s = Evaluator.register_symbol(kind, bind_power)
        s.as_infix = _as_hybrid
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
        if self._current()._kind != "END":  # type: ignore
            raise SyntaxError("Parse error: missing operators?")
        return ret


def roll(formula: str):
    if len(formula) < 1:
        raise ValueError("Roll formula is empty.")
    results = []
    rolls = symbolize(Evaluator.SYMBOL_TABLE, formula)
    for roll in rolls:
        e = Evaluator(roll)
        results.append(e.evaluate())
    return results


def format_roll_results(results: list[Evaluator._Symbol]):
    out = ""
    for row in results:
        final_value = row.final_repr()
        out += (
            codeblock(row.describe())
            + f" ⇒ **{final_value}**"
            + f"  |  {row.describe(evaluated=True, top_level=True)}"
        )
        out += "\n"
    return out


def _dice_operator(node, x, y):
    node.detail = dice_roll(x.get_value(), y.get_value())


def _dice_operator_prefix(node, x):
    node.detail = dice_roll(1, x.get_value())


def assert_set_operands(setr, setsel):
    if not isinstance(setr, SetResult):
        raise SyntaxError("Invalid left operand (not a set)")
    if not isinstance(setsel, SetSelector):
        raise SyntaxError("Invalid right operand (not a selector)")
    return (setr, setsel)


def _set_keep_operator(node, x, y):
    setr, setsel = assert_set_operands(x.detail, y.detail)
    node.detail = set_op_keep(setr, setsel.apply(setr))


def _set_drop_operator(node, x, y):
    setr, setsel = assert_set_operands(x.detail, y.detail)
    node.detail = set_op_keep(setr, setsel.apply(setr), invert=True)


def _set_count_pass_operator(node, x, y):
    setr, setsel = assert_set_operands(x.detail, y.detail)
    node.detail = set_op_count(setr, setsel.apply(setr))


def _set_count_fail_operator(node, x, y):
    setr, setsel = assert_set_operands(x.detail, y.detail)
    node.detail = set_op_count(setr, setsel.apply(setr), invert=True)


def _select_low_operator(node, x):
    node.detail = LowHighSelector(num=x.get_value(), high=False)


def _select_high_operator(node, x):
    node.detail = LowHighSelector(num=x.get_value(), high=True)


def build_selector_nud(selector: SetSelector):
    def _nud(self, ev):
        self.detail = selector
        return self

    return _nud


def _explode_check_right_valid(right: Evaluator._Symbol):
    return right.is_selector()


def _explode_postfix_operator(node, x):
    if not isinstance(x.detail, DiceValues):
        raise SyntaxError("Invalid operand for explode (not a dice result)")
    dice: DiceValues = x.detail
    node.detail = dice_explode(
        dice, ConditionalSelector(lambda a: a >= dice.get_dice_size())
    )


def _explode_infix_operator(node, x, y):
    dice, setsel = assert_set_operands(x.detail, y.detail)
    if not isinstance(dice, DiceValues):
        raise SyntaxError("Invalid operand for explode (not a dice result)")
    node.detail = dice_explode(dice, setsel)


def _explode_once_postfix_operator(node, x):
    if not isinstance(x.detail, DiceValues):
        raise SyntaxError("Invalid operand for explode (not a dice result)")
    dice: DiceValues = x.detail
    node.detail = dice_explode(
        dice, ConditionalSelector(lambda a: a >= dice.get_dice_size()), max_explodes=1
    )


def _explode_once_infix_operator(node, x, y):
    dice, setsel = assert_set_operands(x.detail, y.detail)
    if not isinstance(dice, DiceValues):
        raise SyntaxError("Invalid operand for explode (not a dice result)")
    node.detail = dice_explode(dice, setsel, max_explodes=1)


def _reroll_once_operator(node, x, y):
    dice, setsel = assert_set_operands(x.detail, y.detail)
    if not isinstance(dice, DiceValues):
        raise SyntaxError("Invalid operand for reroll (not a dice result)")
    node.detail = dice_explode(dice, setsel, max_explodes=1, reroll=True)


def _reroll_recursive_operator(node, x, y):
    dice, setsel = assert_set_operands(x.detail, y.detail)
    if not isinstance(dice, DiceValues):
        raise SyntaxError("Invalid operand for reroll (not a dice result)")
    node.detail = dice_explode(dice, setsel, max_explodes=EXPLOSION_CAP, reroll=True)


def _negate_operator(node, x):
    node._value = -x.get_value()


def _factorial_operator(node, x):
    node._value = factorial(x.get_value())


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


def _repeat_function(node, x, y, ev):
    exit_iter_pos = ev.iter_pos

    reps = force_integral(y.get_value(), "repetitions")
    if reps < 0:
        raise ValueError("Cannot repeat negative times")
    if reps == 0:
        node.detail = MultiExpr()
        return

    flats = [
        FlatExpr(
            x.get_value(), x.describe(), x.describe(evaluated=True), x.final_repr()
        )
    ]
    redo_node = x
    for i in range(reps - 1):
        ev._jump_to(ev.token_list.index(node) + 2)  # skip function open paren
        redo_node = ev.expr()
        flats.append(
            FlatExpr(
                redo_node.get_value(),
                redo_node.describe(),
                redo_node.describe(evaluated=True),
                redo_node.final_repr(),
            )
        )
    # jump forward past end of function parentheses
    ev._jump_to(exit_iter_pos)

    node.detail = MultiExpr(flats)


def build_success_lambda(compare_operator, target):
    return lambda x: COMPARISONS[compare_operator](x, target)


# value-value comparison is forced to treat the left-side value as a set containing the single element.
# TODO: vastly simplify this with a different ExprResult class representing 1:1 comparison success/failure.
def build_infix_comparison(operator):
    def _comparison_operator(node, x, y):
        comparison_repr = f"{operator}{y.get_value()}"
        single_set = SuccessValues([x.get_value()])
        selector = ConditionalSelector(
            build_success_lambda(operator, y.get_value()), comparison_repr
        )
        node.detail = set_op_count(single_set, selector.apply(single_set))

    return _comparison_operator


def build_prefix_comparison(operator):
    def _comparison_operator(node, x):
        comparison_repr = f"{operator}{x.get_value()}"
        node.detail = ConditionalSelector(
            build_success_lambda(operator, x.get_value()), comparison_repr
        )

    return _comparison_operator


def build_arithmetic_operator(operator):
    def _arithmetic_operator(node, x, y):
        node._value = ARITHMETICS[operator](x.get_value(), y.get_value())

    return _arithmetic_operator


# Produce a version of this set which is evaluated by aggregating
# using a provided function.
def aggregate_using(setr, agg_func, agg_joiner=", "):
    if not isinstance(setr, SetResult):
        raise SyntaxError("Can't aggregate (operand not a set)")
    return AggregateValues(agg_func, agg_joiner, items=setr.elements)


def _aggregate_function(node, x, y, ev):
    try:
        agg_func = ARITHMETICS[y._kind]
        node.detail = aggregate_using(x.detail, agg_func, y._kind)
    except KeyError as err:
        raise SyntaxError(f"Unknown infix aggregator: {y._kind}") from err


def _reflex_nud(self, ev):
    return self


def _left_paren_nud(self, ev):
    self.first = ev.expr()
    self._value = self.first.get_value()
    self.detail = self.first.detail
    ev.advance(expected=")")
    return self


def _left_brace_nud(self, ev: Evaluator):
    contents = []
    peeked = ev.peek()
    while peeked and peeked._kind != "}":
        content_node: Evaluator._Symbol = ev.expr()
        contents.append(
            FlatExpr(
                content_node.get_value(),
                content_node.describe(),
                content_node.describe(evaluated=True),
                content_node.final_repr(),
            )
        )
        peeked = ev.peek()
        try:
            ev.advance(expected=",")
            peeked = ev.peek()
        except SyntaxError:
            break
    if not peeked:
        raise SyntaxError("Mismatched braces.")
    ev.advance(expected="}")
    self.detail = MultiExpr(contents)
    return self


def build_dash_nud(bind_power):
    def _dash_nud(self, ev):
        follower = ev.peek()
        if follower != None and follower._kind != ")":
            self.first = ev.expr(bind_power)
            self.second = None
            _negate_operator(self, self.first)
        return self

    return _dash_nud


# initialize symbol table with type classes
Evaluator.register_symbol("NUMBER").as_prefix = _reflex_nud  # type: ignore
Evaluator.register_symbol("END")
Evaluator.register_symbol("(").as_prefix = _left_paren_nud  # type: ignore
Evaluator.register_symbol(")")
Evaluator.register_symbol(",")
Evaluator.register_symbol("{").as_prefix = _left_brace_nud  # type: ignore
Evaluator.register_symbol("}")
Evaluator.register_function_double("repeat", _repeat_function)
Evaluator.register_function_single("sqrt", _sqrt_operator)
Evaluator.register_function_single("fact", _factorial_operator)
Evaluator.register_function_double("agg", _aggregate_function)

# Operators given reflex nud to allow their use as agg operands
Evaluator.register_infix(
    "+", build_arithmetic_operator("+"), 10
).as_prefix = _reflex_nud  # type: ignore
Evaluator.register_infix(
    "-", build_arithmetic_operator("-"), 10
).as_prefix = build_dash_nud(  # dash nud special case because of negation prefix
    100
)  # type: ignore
Evaluator.register_infix(
    "*", build_arithmetic_operator("*"), 20
).as_prefix = _reflex_nud  # type: ignore
Evaluator.register_infix("×", build_arithmetic_operator("*"), 20)
Evaluator.register_infix(
    "/", build_arithmetic_operator("/"), 20
).as_prefix = _reflex_nud  # type: ignore
Evaluator.register_infix("÷", build_arithmetic_operator("/"), 20)
Evaluator.register_infix(
    "%", build_arithmetic_operator("%"), 20
).as_prefix = _reflex_nud  # type: ignore

Evaluator.register_infix(
    "^", build_arithmetic_operator("^"), 110, right_assoc=True
).as_prefix = _reflex_nud  # type: ignore

Evaluator.register_infix("C", _choose_operator, 130, spaces=True)
Evaluator.register_infix("choose", _choose_operator, 130, spaces=True)

# Set Operators
Evaluator.register_infix("k", _set_keep_operator, 180)
Evaluator.register_infix("p", _set_drop_operator, 180)
Evaluator.register_infix("?", _set_count_pass_operator, 180)
Evaluator.register_infix("~?", _set_count_fail_operator, 180)
Evaluator.register_hybrid_infix_postfix(
    "!",
    _explode_infix_operator,
    _explode_postfix_operator,
    _explode_check_right_valid,
    180,
).should_postfix = (
    lambda self: self._kind == "!" and self.second is None
)
Evaluator.register_hybrid_infix_postfix(
    "!o",
    _explode_once_infix_operator,
    _explode_once_postfix_operator,
    _explode_check_right_valid,
    180,
).should_postfix = (
    lambda self: self._kind == "!o" and self.second is None
)
Evaluator.register_infix("r", _reroll_once_operator, 180)
Evaluator.register_infix("rr", _reroll_recursive_operator, 180)

# Set Selectors
Evaluator.register_prefix("h", _select_high_operator, 190)
Evaluator.register_prefix("l", _select_low_operator, 190)
Evaluator.register_symbol("even").as_prefix = build_selector_nud(EvenOddSelector(odd=False))  # type: ignore
Evaluator.register_symbol("odd").as_prefix = build_selector_nud(EvenOddSelector(odd=True))  # type: ignore

# Comparisons
for comp in COMPARISONS.keys():
    Evaluator.register_infix(comp, build_infix_comparison(comp), 5)
for comp in COMPARISONS.keys():
    Evaluator.register_prefix(
        comp, build_prefix_comparison(comp), 190
    ).should_spaces = (lambda self: self.second != None)

# Dice
Evaluator.register_infix("d", _dice_operator, 200)
Evaluator.register_prefix("d", _dice_operator_prefix, 200)

if __name__ == "__main__":
    while True:
        intext = input()
        try:
            symbols = symbolize(Evaluator.SYMBOL_TABLE, intext)
            print(symbols)
            results = roll(intext)
            print(format_roll_results(results))
        except (
            ArithmeticError,
            ValueError,
            RuntimeError,
            StopIteration,
            SyntaxError,
        ) as err:
            print(f"{err}")
