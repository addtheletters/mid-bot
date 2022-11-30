import itertools
import typing
from functools import total_ordering
from random import randint

EXPLOSION_CAP = 99


def force_integral(value, description="") -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    else:
        raise ValueError(f"Expected integer # {description}: {value}")


# Represents the value of one element in a set.
# Tracks whether or not it has been dropped or added to the set.
class SetElement(typing.NamedTuple):
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
    def __init__(self, items: list | None = None):
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
        self.result_value = self

    def __repr__(self):
        return f"{len(self.elements)} element" + (
            "s" if len(self.elements) != 1 else ""
        )

    def __iter__(self):
        return iter(self.get_remaining())

    def copy(self):
        return SetResult(items=self.elements.copy())

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


class DiceValues(SetResult):
    def __init__(self, dice_size, items):
        super().__init__(items)
        self.dice_size = dice_size
        self.set_value(self.total())

    def __repr__(self):
        return str(self.get_value())

    def copy(self):
        return DiceValues(self.dice_size, self.elements)

    # Override to wrap and use `+` to join.
    def get_description(self):
        return "(" + super().get_description(joiner="+") + ")=" + str(self.get_value())

    def get_dice_size(self):
        return self.dice_size


# The result of a conditional filter applied to collected values, conceptually
# some number of dice rolls that successful meet some operator's condition.
# Total value is evaluated to the number of non-dropped items remaining.
class SuccessValues(SetResult):
    def __init__(self, items):
        super().__init__(items)

    def __repr__(self):
        return f"{self.get_value()} success" + ("es" if self.get_value() != 1 else "")

    def copy(self):
        return SuccessValues(self.elements)

    def get_value(self):
        return self.get_remaining_count()

    def get_description(self):
        return "(" + super().get_description() + ")⇒" + str(self)


class SetSelector(ExprResult):
    # Override. Repr with description, since has no value.
    def __repr__(self):
        return self.get_description()

    # Override.
    def get_value(self):
        raise SyntaxError(
            f"Can't get value of a set selector: {self.get_description()}"
        )

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
            super().__init__(condition=lambda x: (x % 2 != 0), cond_repr="odd")
        else:
            super().__init__(condition=lambda x: (x % 2 == 0), cond_repr="even")


def invert_selection(all_count: int, selected: list[int]):
    return [i for i in range(all_count) if i not in selected]


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


# Set operator.
# Returns the set with value as the number of selected items.
# Drops items not matched by the selector.
# `invert` inverts the behavior, dropping matched items and counting unmatched ones.
def set_op_count(setr: SetResult, selected: list[int], invert=False):
    count = setr.get_remaining_count() - len(selected)
    to_drop = selected
    if not invert:
        count = len(selected)
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


# Set operator for dice.
# Roll another die for any matches and add it to the total.
# For new dice added this way, each match adds yet another die, up to `max_explodes` times.
def dice_explode(dice: DiceValues, selector: SetSelector, max_explodes=EXPLOSION_CAP):
    new_dice = dice.copy()

    explosions = 0
    should_explode = selector.apply(new_dice)
    exploded_values: list = []
    has_exploded: list[int] = []

    while explosions < max_explodes and len(should_explode) > 0:
        for i in should_explode:
            exploded_values.append(single_roll(new_dice.dice_size))
            has_exploded.append(i)

        explosions += 1
        new_dice.add_items(exploded_values)
        exploded_values = []
        # this is not very performant. TODO have the selector apply to only the new values
        should_explode = [i for i in selector.apply(new_dice) if i not in has_exploded]

    new_dice.set_value(new_dice.total())
    return new_dice
