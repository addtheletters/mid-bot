# Dicerolling.
# Parser and evaluator for dice roll inputs.

from typing import NamedTuple
import itertools
import re
from functools import total_ordering
from math import factorial, sqrt
from random import randint
import typing

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
    ("OP",       r"[+\-*×/÷%^()]"),             # Generic operators
    ("SEP",      r"[,]"),                       # Separators like commas
    ("END",      r"[;\n]"),                     # Line end / break characters
    ("SKIP",     r"[ \t]+"),                    # Skip over spaces and tabs
    ("MISMATCH", r"."),                         # Any other character
]
TOKEN_PATTERN = re.compile(
    '|'.join(f"(?P<{pair[0]}>{pair[1]})" for pair in TOKEN_SPEC))
# fmt: on

EXPLOSION_CAP = 9999

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


def force_integral(value, description="") -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    else:
        raise ValueError(f"Expected integer # {description}: {value}")


def single_roll(size) -> int:
    if size == 0:
        return 0
    else:
        return randint(1, size)


def dice_roll(count, size):
    count = force_integral(count, "dice count")
    if size < 0:
        raise ValueError(f"Negative dice don't exist (d{size})")
    size = force_integral(size, "dice size")
    if count < 0:
        raise ValueError(f"Can't roll a negative number of dice ({count})")

    rolls = []
    for i in range(count):
        rolls.append(single_roll(size))

    return DiceValues(size, items=rolls)


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
        if n < 0:  # allow keeping more dice than are rolled (drop none)
            n = 0
    if n < 0:
        raise ValueError(f"Can't drop negative # of items ({n})")

    new_values = dice.copy()
    if n == 0:
        # nothing to drop
        return new_values

    # sort and pair with indices
    sdice = sorted(
        list(enumerate(dice.get_all_items())), key=lambda x: x[1], reverse=high ^ keep
    )
    # remove already dropped
    sdice = list(filter(lambda x: x[0] not in dice.dropped, sdice))
    # find n more to drop
    new_drops = [x[0] for x in sdice[:n]]

    new_values.dropped.extend(new_drops)
    return new_values


# def dice_explode(dice, condition=None, max_explosion=EXPLOSION_CAP):
#     if not isinstance(dice, DiceValues):
#         raise SyntaxError(f"Can't explode (not dice)")
#     if condition == None:
#         condition = lambda x: (x >= dice.dice_size)

#     new_values = dice.copy()
#     rolls = new_values.get_all_items()

#     exploded = []
#     exploded_indices = []
#     for i in range(len(rolls)):
#         if i in dice.dropped:
#             continue
#         if condition(rolls[i]) and len(exploded) < max_explosion:
#             exploded_indices.append(len(rolls) + len(exploded))
#             exploded.append(single_roll(dice.dice_size))

#     i = 0
#     while i < len(exploded) and len(exploded) < max_explosion:
#         if condition(exploded[i]):
#             exploded_indices.append(len(rolls) + len(exploded))
#             exploded.append(single_roll(dice.dice_size))
#         i += 1

#     new_values.items.extend(exploded)
#     new_values.added.extend(exploded_indices)
#     return new_values


# Look through collected values. Drop any that don't succeed the condition.
# `condition` should be a lambda function returning True for a success.
def success_filter(dice, condition):
    if not isinstance(dice, CollectedValues):
        raise SyntaxError("Can't filter for successes (operand not a collection)")

    new_values = SuccessValues(items=dice.items, dropped=dice.dropped, added=dice.added)
    failures = []
    for pair in enumerate(dice.get_remaining()):
        if not condition(pair[1]):
            failures.append(pair[0])
    new_values.dropped.extend(failures)
    return new_values


# Produce a version of this collection which is evaluated by aggregating
# using a provided function.
def aggregate_using(collected, agg_func, agg_joiner=", "):
    if not isinstance(collected, CollectedValues):
        raise SyntaxError("Can't aggregate (operand not a collection)")

    new_values = AggregateValues(
        agg_func,
        agg_joiner,
        items=collected.items,
        dropped=collected.dropped,
        added=collected.added,
    )
    return new_values


# Represents the value of one element in a set.
# Tracks whether or not it has been dropped or added to the set.
class SetElement(NamedTuple):
    item: typing.Any
    dropped: bool = False
    added: bool = False

    def formatted(self, text=None) -> str:
        if text is None:
            text = ExprResult.description(self.item)
        if self.dropped:  # strikethrough dropped values
            text = f"~~{text}~~"
        if self.added:  # italicize added values
            text = f"_{text}_"
        return text


# The result of evaluating an expression, to be stored in a parse tree node
# which required computation or collection. This is for operations with
# complexity that cannot be represented by formatting just the operator and
# operands.
class ExprResult:

    # repr will be how this expression's final result will be shown
    def __repr__(self):
        return str(self.get_value())

    # Helpers allowing literal values and ExprResult instances to be handled
    # by a single code path
    @staticmethod
    def value(item):
        if isinstance(item, ExprResult):
            return item.get_value()
        elif isinstance(item, SetElement):
            return item.item
        return item

    @staticmethod
    def description(item):
        if isinstance(item, ExprResult):
            return item.get_description()
        elif isinstance(item, SetElement):
            return ExprResult.description(item.item)
        return f"{item}"

    # Numerical value for this expression.
    def get_value(self):
        raise NotImplementedError("Value missing for this expression.")

    # String description of how this expression was evaluated.
    def get_description(self) -> str:
        raise NotImplementedError("Description missing for this expression.")


# Represents an expression which resolved to a single value,
# storing only the final value and description strings.
@total_ordering
class FlatExpr(ExprResult):
    def __init__(self, value, description, subrepr):
        self.value = value
        self.description = description
        self.subrepr = subrepr

    def __repr__(self):
        if self.subrepr:
            return self.subrepr
        return super().__repr__()

    def get_value(self):
        return self.value

    def get_description(self):
        return self.description

    def __eq__(self, other):
        return self.value == ExprResult.value(other)

    def __lt__(self, other):
        return self.value < ExprResult.value(other)


# For representing a collection of elements upon which set operations may be performed.
# "Set" is a misnomer shorthand for these collections, since they are ordered.
# Selectors return lists of element indices and operators take those indices as input.
# `items` are expected to be repr'able, as a literal or ExprResult.
class SetResult(ExprResult):
    def __init__(self, items: list | None = None, operator=None, selector=None):
        super().__init__()
        # create SetElements for each input item, unless already provided with SetElements (copying from another set)
        self.elements: list[SetElement] = (
            [
                (item if isinstance(item, SetElement) else SetElement(item=item))
                for item in items
            ]
            if items
            else []
        )
        self.selector: typing.Callable[[SetResult], list[int]] | None = selector
        self.operator: typing.Callable[
            [SetResult, list[int]], typing.Any
        ] | None = operator
        self.result_value = self

    def __repr__(self):
        return f"{len(self.elements)} element" + (
            "s" if len(self.elements) != 1 else ""
        )

    def __iter__(self):
        return iter(self.get_remaining())

    def copy(self):
        return SetResult(
            items=self.elements.copy(),
            operator=self.operator,
            selector=self.selector,
        )

    # def _do_operator(self):
    #     if self.operator == None:
    #         return None
    #     selected = []
    #     if self.selector != None:
    #         selected = self.selector(self)
    #     else:
    #         # select all remaining if no selector is provided
    #         selected = [i for (i, _) in self.get_remaining_enumerated()]
    #     return self.operator(self, selected)

    def set_value(self, value):
        self.result_value = value

    # Override. If no result value has been set, returns itself as a full set.
    def get_value(self):
        return self.result_value

    # Override. List collection contents.
    def get_description(self, joiner=", "):
        return joiner.join([self.format_element(element) for element in self.elements])

    # Can be overridden for customized per-element formatting.
    def format_element(self, element: SetElement):
        return element.formatted()

    # Returns the number of items, including dropped ones.
    def get_all_count(self):
        return len(self.elements)

    # Returns all items, including dropped ones.
    def get_all_items(self):
        return [element.item for element in self.elements]

    # Exclude dropped items.
    def get_remaining(self):
        return [element.item for element in self.elements if element.dropped == False]

    def get_remaining_count(self):
        return len(self.get_remaining())

    # Return a list of all tuples of (index, non-dropped item).
    def get_remaining_enumerated(self):
        return [
            (fpair[0], fpair[1].item)
            for fpair in filter(
                lambda pair: not pair[1].dropped,
                enumerate(self.elements),
            )
        ]

    # Aggregate together non-dropped items.
    # If `func` remains None, default behavior is a sum.
    def aggregate(self, func=None):
        values = [ExprResult.value(item) for item in self.get_remaining()]
        return list(itertools.accumulate(values, func))

    def total(self, func=None):
        if self.get_remaining_count() < 1:
            return 0
        return self.aggregate(func)[-1]  # TODO replace with itertools.reduce?

    # Drop items located at specific indices
    def drop_indices(self, indices: list[int]):
        for i in indices:
            self.elements[i] = SetElement(
                item=self.elements[i].item, dropped=True, added=self.elements[i].added
            )

    # Add items as new set elements
    def add_items(self, items: list):
        for item in items:
            self.elements.append(SetElement(item=item, dropped=False, added=True))


class SetSelector(ExprResult):
    # Override. Repr with description, since has no value.
    def __repr__(self):
        return self.get_description()
        
    # Override.
    def get_value(self):
        raise SyntaxError("Can't get value of a set selector.")

    # Returns a list of indices of elements matched by the selector.
    def apply(self, setr: SetResult) -> list[int]:
        raise NotImplementedError("Set selector behavior is missing.")


# Set selector. Finds all items satisfying the condition.
# Returns a list of indices of elements that match.
class ConditionalSelector(SetSelector):
    def __init__(
        self, condition: typing.Callable[..., bool], cond_repr: str = "(? condition)"
    ) -> None:
        super().__init__()
        self.condition = condition
        self.cond_repr = cond_repr

    def get_description(self) -> str:
        return self.cond_repr

    def apply(self, setr: SetResult) -> list[int]:
        return _select_conditional(setr, self.condition)


def _select_conditional(
    setr: SetResult, condition: typing.Callable[..., bool]
) -> list[int]:
    elements = setr.get_remaining_enumerated()
    matched_pairs = list(filter(lambda pair: condition(pair[1]), elements))
    return [pair[0] for pair in matched_pairs]


# Set selector. Finds the `n` lowest or highest values in the set.
# `high` value of False means selecting the lowest items.
class LowHighSelector(SetSelector):
    def __init__(self, num: int = 1, high: bool = False) -> None:
        super().__init__()
        self.num: int = num
        self.high: bool = high

    def get_description(self) -> str:
        return f"{'h' if self.high else 'l'}{self.num}"

    def apply(self, setr: SetResult) -> list[int]:
        return _select_low_high(setr, self.num, self.high)


def _select_low_high(setr: SetResult, n: int, high: bool = False) -> list[int]:
    n = force_integral(n, "items to drop")
    if n < 0:
        raise ValueError(f"Can't drop negative # of items ({n})")
    if n == 0:
        # nothing to select
        return []

    # sort and pair with indices
    sorted_pairs = sorted(
        setr.get_remaining_enumerated(), key=lambda pair: pair[1], reverse=high
    )
    # gather indices of n elements
    return [pair[0] for pair in sorted_pairs[:n]]


class EvenOddSelector(ConditionalSelector):
    def __init__(self, odd: bool = False) -> None:
        self.odd = odd
        if odd:
            super().__init__(condition=lambda x: (x % 2 == 0), cond_repr="odd")
        else:
            super().__init__(condition=lambda x: (x % 2 != 0), cond_repr="even")


def invert_selection(all_count: int, selected: list[int]):
    return [i for i in range(all_count) if i not in selected]


# Set operator.
# Returns the set with value as the number of selected items.
# Drops items not matched by the selector.
# `invert` inverts the behavior, dropping matched items and counting unmatched ones.
def set_op_count(setr: SetResult, selected: list[int], invert=False):
    count = len(selected)
    to_drop = selected
    if not invert:
        count = setr.get_remaining_count() - len(selected)
        to_drop = invert_selection(setr.get_all_count(), selected)
    setr.drop_indices(to_drop)
    setr.set_value(count)
    return setr


# Set operator.
# Returns the set with value as the sum of selected items.
# Drops items not matched by the selector.
# `invert` inverts the behavior, dropping matched items and adding unmatched ones.
def set_op_keep(setr: SetResult, selected: list[int], invert=False):
    to_drop = selected
    if not invert:
        to_drop = invert_selection(setr.get_all_count(), selected)
    setr.drop_indices(to_drop)
    setr.set_value(setr.total())
    return setr


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
        return f"{len(self.items)} item" + ("s" if len(self.items) != 1 else "")

    def copy(self):
        return CollectedValues(
            self.items.copy(), self.dropped.copy(), self.added.copy()
        )

    # Override. Default to returning the sum of non-dropped items.
    def get_value(self):
        return self.total()

    def format_item(self, base, index, formatting=True):
        if not formatting:
            return base
        if index in self.dropped:
            base = f"~~{base}~~"
        if index in self.added:
            base = f"_{base}_"
        return base

    # Override to list collection contents.
    def get_description(self, joiner=", "):
        out = joiner.join(
            [
                self.format_item(ExprResult.description(self.items[i]), i)
                for i in range(len(self.items))
            ]
        )
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
        values = [ExprResult.value(x) for x in self.get_remaining()]
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
                added=copy_source.added.copy(),
            )
        else:
            super().__init__(items=contents)

    def __repr__(self):
        remain_count = self.get_remaining_count()
        return f"{remain_count} result" + ("s" if remain_count != 1 else "")

    def copy(self):
        return MultiExpr(copy_source=self)

    def get_value(self):
        if self.get_remaining_count() == 1:
            return self.get_remaining()[0].get_value()
        return None

    def get_description(self, joiner="\n"):
        out = "{\n"
        out += joiner.join(
            [
                self.format_item(
                    f"**{str(self.items[i])}**  |  {ExprResult.description(self.items[i])}",
                    i,
                )
                for i in range(len(self.items))
            ]
        )
        return out + "\n}"


class DiceValues(SetResult):
    def __init__(self, dice_size, items):
        super().__init__(items)
        self.dice_size = dice_size
        self.set_value(self.total())

    def __repr__(self):
        return str(self.get_value())

    def copy(self):
        return DiceValues(
            self.dice_size, self.elements
        )

    # Override to wrap and use `+` to join.
    def get_description(self):
        return "(" + super().get_description(joiner="+") + ")=" + str(self.get_value())

    def get_dice_size(self):
        return self.dice_size


# The result of a conditional filter applied to collected values, conceptually
# some number of dice rolls that successful meet some operator's condition.
# Total value is evaluated to the number of non-dropped items remaining.
class SuccessValues(CollectedValues):
    def __init__(self, items=None, dropped=None, added=None):
        super().__init__(items, dropped, added)

    def __repr__(self):
        return f"{self.get_value()} success" + ("es" if self.get_value() != 1 else "")

    def copy(self):
        return SuccessValues(self.items.copy(), self.dropped.copy(), self.added.copy())

    def get_value(self):
        return self.get_remaining_count()

    def get_description(self):
        return "(" + super().get_description() + ")⇒" + str(self)


class AggregateValues(CollectedValues):
    def __init__(self, agg_func, agg_joiner, items=None, dropped=None, added=None):
        super().__init__(items, dropped, added)
        self.agg_func = agg_func  # lambda function to aggregate with
        self.agg_joiner = agg_joiner  # string representing operator used to aggregate

    def __repr__(self):
        return str(self.get_value())

    def copy(self):
        return AggregateValues(
            self.agg_func,
            self.agg_joiner,
            self.items.copy(),
            self.dropped.copy(),
            self.added.copy(),
        )

    # Override to apply aggregate operation.
    def total(self):
        return super().total(func=self.agg_func)

    # Override to wrap items in parens if necessary.
    def format_item(self, base, index):
        wrap = base
        if (
            isinstance(self.items[index], ExprResult)
            and (base[0] != "(" or base[-1] != ")")
            and (base[0] != "[" or base[-1] != "]")
        ):
            wrap = "(" + base + ")"
        return super().format_item(wrap, index)

    # Override to use appropriate joiner. Assume all aggregation operators are
    # infix.
    def get_description(self):
        # We could append = (total) for consistency with dice rolls.
        # Some tweaks to describe() would be needed, as a special case
        # for `agg` but not `d` causes differences in formatting paths.
        return "(" + super().get_description(joiner=escape(self.agg_joiner)) + ")"


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

    def peek(self):
        try:
            peeked = self.token_list[self.iter_pos]
        except IndexError:
            return None
        return peeked

    def advance(self, expected=None):
        if expected and self._current()._kind != expected:  # type: ignore
            raise SyntaxError(f"Missing expected: {expected}")
        return self._next()

    # Syntax tree base class
    class _Symbol:
        # token type.
        _kind = None
        # operator binding power, 0 for literals.
        _bp = 0

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
            describe_first = (
                self.first.describe(
                    uneval=uneval,
                    predrop=(
                        self.is_dropkeepadd() or (predrop and self.is_collection())
                    ),
                )
                if self.first != None
                else ""
            )
            describe_second = (
                self.second.describe(uneval=uneval) if self.second != None else ""
            )

            if self._kind == "(":  # parenthesis group
                return "(" + describe_first + ")"

            spacer = " " if self._spaces else ""
            detail_description = ""

            if not uneval:
                if (not self.is_collection()) and (not self.contains_diceroll()):
                    # No child contains diceroll randomness, so just show the
                    # value; or other repr if valueless like an operator
                    # argument.
                    if self.get_value() == None:
                        return escape(str(self))
                    return f"{self.get_value()}"

                # repeated expression special case
                # This causes details to be hidden from `agg`.
                if (self._kind == "repeat" or self._kind == "agg") and (not predrop):
                    return ExprResult.description(self.detail)

                if self.detail:
                    detail_description = " " + ExprResult.description(self.detail)
                if self.is_collection():
                    # Hide breakout detail description if only one item
                    if (
                        len(self.detail.get_all_items()) < 2  # type: ignore
                        and self.detail.get_value() != None  # type: ignore
                    ):
                        detail_description = "⇒" + str(self.detail)
                    # Hide details if outer collection already will show them
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

            prewrap = f"{left}{spacer}{op}{spacer}{right}" + f"{detail_description}"

            if self._kind == "choose" or self._kind == "C":
                return "(" + prewrap + ")"
            elif self.is_collection() and not (predrop or uneval):
                return "[" + prewrap + "]"
            return prewrap

        def __repr__(self):
            if self._kind == "NUMBER":
                return f"{self._value}"
            if self._kind in ARITHMETICS.keys():
                return self._kind
            out = [self._kind, self.first, self.second]
            out = map(str, filter(None, out))
            return "<" + " ".join(out) + ">"

        def final_repr(self):
            if self.detail != None:
                return str(self.detail)
            final_value = self.get_value()
            if final_value == None:
                return str(self)
            return str(final_value)

        def is_collection(self):
            if self.detail != None and isinstance(self.detail, CollectedValues):
                return True
            return False

        def is_diceroll(self):
            return self._kind == "d" or self.is_dropkeepadd()

        def is_dropkeepadd(self):
            return self._kind in (
                "p",
                "k",
                "l",
                "h",
                "!",
                "!>",
                "!<",
                "!>=",
                "!<=",
                "!=",
                "?>",
                "?<",
                "?>=",
                "?<=",
                "?=",
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
    def register_infix(kind, func, bind_power, right_assoc=False):
        def _as_infix(self, evaluator, left):
            self.first = left
            self.second = evaluator.expr(bind_power - (1 if right_assoc else 0))
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


def format_roll_results(results):
    out = ""
    for row in results:
        final_value = row.final_repr()
        out += (
            codeblock(row.describe(uneval=True))
            + f" ⇒ **{final_value}**"
            + f"  |  {row.describe()}"
        )
        out += "\n"
    return out


def _dice_operator(node, x, y):
    node.detail = dice_roll(x.get_value(), y.get_value())


def _dice_operator_prefix(node, x):
    node.detail = dice_roll(1, x.get_value())


def _set_keep_operator(node, x, y):
    if not isinstance(x.detail, SetResult):
        raise SyntaxError("Can't drop/keep (left operand is not a set)")
    if not isinstance(y.detail, SetSelector):
        raise SyntaxError("Can't drop/keep (right operand is not a selector)")
    node.detail = set_op_keep(x.detail.copy(), y.detail.apply(x.detail))


def _set_drop_operator(node, x, y):
    if not isinstance(x.detail, SetResult):
        raise SyntaxError("Can't drop/keep (left operand is not a set)")
    if not isinstance(y.detail, SetSelector):
        raise SyntaxError("Can't drop/keep (right operand is not a selector)")
    node.detail = set_op_keep(x.detail.copy(), y.detail.apply(x.detail), invert=True)


def _select_low_operator(node, x):
    node.detail = LowHighSelector(num=x.get_value(), high=False)


def _select_high_operator(node, x):
    node.detail = LowHighSelector(num=x.get_value(), high=True)


def _negate_operator(node, x):
    node._value = -x.get_value()


def _factorial_operator(node, x):
    node._value = factorial(x.get_value())


# def _dice_explode_operator(node, x):
#     node.detail = dice_explode(x.detail)


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

    flats = [FlatExpr(x.get_value(), x.describe(), x.final_repr())]
    redo_node = x
    for i in range(reps - 1):
        ev._jump_to(ev.token_list.index(node) + 2)  # skip function open paren
        redo_node = ev.expr()
        flats.append(
            FlatExpr(
                redo_node.get_value(), redo_node.describe(), redo_node.final_repr()
            )
        )
    # jump forward past end of function parentheses
    ev._jump_to(exit_iter_pos)

    node.detail = MultiExpr(contents=flats)


def build_success_lambda(compare_operator, target):
    return lambda x: COMPARISONS[compare_operator](x, target)


def build_comparison_operator(operator):
    def _comparison_operator(node, x, y):
        grouping = SuccessValues(items=[x.get_value()])
        node.detail = success_filter(
            grouping, build_success_lambda(operator, y.get_value())
        )

    return _comparison_operator


def build_comparison_filter(operator):
    def _comparison_filter(node, x, y):
        node.detail = success_filter(
            x.detail, build_success_lambda(operator, y.get_value())
        )

    return _comparison_filter


# def build_comparison_exploder(operator):
#     def _explode_compare_operator(node, x, y):
#         node.detail = dice_explode(
#             x.detail, build_success_lambda(operator, y.get_value())
#         )

#     return _explode_compare_operator


def build_arithmetic_operator(operator):
    def _arithmetic_operator(node, x, y):
        node._value = ARITHMETICS[operator](x.get_value(), y.get_value())

    return _arithmetic_operator


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
Evaluator.register_function_double("repeat", _repeat_function)
Evaluator.register_function_single("sqrt", _sqrt_operator)
Evaluator.register_function_single("fact", _factorial_operator)
Evaluator.register_function_double("agg", _aggregate_function)

for comp in COMPARISONS.keys():
    Evaluator.register_infix(comp, build_comparison_operator(comp), 5)._spaces = True

# Operators given reflex nud to allow their use as agg operands
Evaluator.register_infix(
    "+", build_arithmetic_operator("+"), 10
).as_prefix = _reflex_nud  # type: ignore
# dash nud special case because of negation prefix
Evaluator.register_infix("-", build_arithmetic_operator("-"), 10)
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

Evaluator.register_symbol("-").as_prefix = build_dash_nud(100)  # type: ignore
Evaluator.register_infix(
    "^", build_arithmetic_operator("^"), 110, right_assoc=True
).as_prefix = _reflex_nud  # type: ignore

Evaluator.register_infix("C", _choose_operator, 130)._spaces = True
Evaluator.register_infix("choose", _choose_operator, 130)._spaces = True

# for comp in COMPARISONS.keys():
#     Evaluator.register_infix("!" + comp, build_comparison_exploder(comp), 190)

# Evaluator.register_postfix("!", _dice_explode_operator, 190)

for comp in COMPARISONS.keys():
    Evaluator.register_infix("?" + comp, build_comparison_filter(comp), 190)

# Evaluator.register_infix("dl", _drop_low_operator, 190)
# Evaluator.register_infix("dh", _drop_high_operator, 190)
# Evaluator.register_infix("kl", _keep_low_operator, 190)
# Evaluator.register_infix("kh", _keep_high_operator, 190)

Evaluator.register_prefix("h", _select_high_operator, 190)
Evaluator.register_prefix("l", _select_low_operator, 190)
Evaluator.register_infix("k", _set_keep_operator, 180)
Evaluator.register_infix("p", _set_drop_operator, 180)

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
