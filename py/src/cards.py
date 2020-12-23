# Cards.
# Decks and dealing.
from collections import namedtuple
from functools import total_ordering
import random
import re

BIG_JOKER_SUIT_CHAR = "(big)"
BIG_JOKER_SUIT = 2
SMALL_JOKER_SUIT_CHAR = "(small)"
SMALL_JOKER_SUIT = 1
JOKER_NUMBER = 15
JOKER_NUMBER_CHAR = 'joker'


@total_ordering
class Card(namedtuple("CardId", ["n", "s"])):
    NUMBERS = ['2', '3', '4', '5', '6', '7',
               '8', '9', '10', 'J', 'Q', 'K', 'A']
    SUITS = ['♣', '♦', '♥', '♠']
    SPECIAL = {
        (JOKER_NUMBER, 1): "SMALL_JOKER",
        (JOKER_NUMBER, 2): "BIG_JOKER",
    }

    def is_valid(self):
        if self.n < 0 or self.s < 0\
            or ((self.n >= len(Card.NUMBERS)
                 or self.s >= len(Card.SUITS))
                and (self.n, self.s) not in Card.SPECIAL):
            return False
        return True

    def number(self):
        if (self.n, self.s) in Card.SPECIAL:
            if self.n == JOKER_NUMBER:
                return JOKER_NUMBER_CHAR
        return Card.NUMBERS[self.n]

    def suit(self):
        if (self.n, self.s) in Card.SPECIAL:
            if self.s == 1:
                return SMALL_JOKER_SUIT_CHAR
            elif self.s == 2:
                return BIG_JOKER_SUIT_CHAR
            return None
        return Card.SUITS[self.s]

    def unicode(self):
        # not yet implemented
        return

    def set_label(self, label):
        self.label = label

    def __lt__(self, other):
        if self.n != other.n:
            return self.n < other.n
        else:
            return self.s < other.s

    def __eq__(self, other):
        return (self.n == other.n) and (self.s == other.s)

    def __repr__(self):
        return f"{self.number()}{self.suit()}"

    @staticmethod
    def big_joker():
        return Card(JOKER_NUMBER, BIG_JOKER_SUIT)

    @staticmethod
    def small_joker():
        return Card(JOKER_NUMBER, SMALL_JOKER_SUIT)


class CustomCard():
    def __init__(self, label):
        self.label = label


def build_deck_52():
    deck = []
    for suit in range(len(Card.SUITS)):
        for num in range(len(Card.NUMBERS)):
            deck.append(Card(num, suit))
    return deck


def build_deck_54():
    deck = build_deck_52()
    deck.append(Card.big_joker())
    deck.append(Card.small_joker())
    return deck


def shuffle(deck):
    random.shuffle(deck)
    return deck


def draw(deck, count=1):
    drawn = []
    try:
        for i in range(count):
            drawn.append(deck.pop())
    except IndexError as err:
        print("Deck has no more cards to draw.")
    return drawn

def create_card(card_string):
    rank = None
    suit = None

    matches = re.match("\d+\w+", card_string)
    if matches[0] and matches[0] in Card.NUMBERS:
        rank = matches[0]
    if matches[1] and matches[1] in Card.SUITS:
        suit = matches[1]

    if rank and suit:
        card = Card(rank, suit)
        card.set_label(card_string)
        return card
    return CustomCard(card_string)


if __name__ == "__main__":
    deck = build_deck_54()
    for card in deck:
        print(card)
    print("========")
    shuffle(deck)
    print(draw(deck, 5))
