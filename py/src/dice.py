# Dicerolling.
# Parser and evaluator for dice roll inputs.

def parse(intext):
    return []

def evaluate(parse_tree):
    return 0

def roll(intext):
    try:
        tree = parse_dice(intext)
        result = compute_roll(tree)
    except:
        print(f"Dice roll failed on: {intext}")
        raise
    return result

def format_roll_result(result):
    return f"{result}"
