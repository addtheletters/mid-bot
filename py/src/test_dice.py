import unittest

import dice, dice_details


class RollTest(unittest.TestCase):
    def assertFirstRollEquals(self, roll_input, expected):
        results = dice.roll(roll_input)
        self.assertAlmostEqual(results[0].get_value(), expected)

    def assertFormattingEquals(self, roll_input, expected):
        results = dice.roll(roll_input)
        self.assertEqual(dice.format_roll_results(results), expected)


class MathTest(RollTest):
    def test_basic_arithmetic(self):
        self.assertFirstRollEquals("1+2", 3)
        self.assertFirstRollEquals("2 * 4", 8)
        self.assertFirstRollEquals("10 / 2", 5)
        self.assertFirstRollEquals("15%4", 3)

    def test_complex_arithmetic(self):
        self.assertFirstRollEquals("(3.5) * (100 - 90)", 35)
        self.assertFirstRollEquals("4 × (5 + 3)", 32)
        self.assertFirstRollEquals("5*2^2", 20)
        self.assertFirstRollEquals("30 ÷ 5 × 3", 18)
        self.assertFirstRollEquals("4*2.5 + 8.5+1.5 / 3.0", 19)
        self.assertFirstRollEquals("sqrt(16)", 4)
        self.assertFirstRollEquals("9%4+sqrt(15)", 4.872983346207417)

    def test_combinatorics(self):
        self.assertFirstRollEquals("fact(6)", 720)
        self.assertFirstRollEquals("10 choose 5", 252)
        self.assertFirstRollEquals("5C2", 10)
        self.assertFirstRollEquals("5 C fact(2)", 10)
        self.assertFirstRollEquals("fact(5C2)", 3628800)
        self.assertFirstRollEquals("12 P 2", 132)
        self.assertFirstRollEquals("30 permute 5", 17100720)

    def test_comparison(self):
        self.assertFirstRollEquals("10 > 3", True)
        self.assertFirstRollEquals("10 >= 3", True)
        self.assertFirstRollEquals("10 < 3", False)
        self.assertFirstRollEquals("10 <= 3", False)
        self.assertFirstRollEquals("10 ~= 3", True)
        self.assertFirstRollEquals("10 = 3", False)

    def test_floor_division(self):
        self.assertFirstRollEquals("10 // 3", 3)
        self.assertFirstRollEquals("12 // 4", 3)

    # Test that semicolons separate an input into multiple rolls.
    def test_breaks(self):
        results = dice.roll("1d20+5; 2d6+5")
        self.assertEqual(len(results), 2)
        results = dice.roll("1+5d2;(2d9)*3;15")
        self.assertEqual(len(results), 3)


class DiceTest(RollTest):
    def test_interpret_diceroll(self):
        dice.roll("d10")
        dice.roll("3d20")
        dice.roll("8d6")
        dice.roll("10C4d3")
        dice.roll("(10C4)d3")
        dice.roll("10 - 10d4")
        dice.roll("3d((2+23)/5)")

    def test_interpret_dropkeep(self):
        dice.roll("4d6kh3")
        dice.roll("8d12pl3")
        dice.roll("30d10pl1kh5pl2")

    def test_interpret_dice_select_compare(self):
        dice.roll("10d8k>4")
        dice.roll("10d8k>=4")
        dice.roll("10d8k<4")
        dice.roll("10d8k<=4")
        dice.roll("10d8k~=4")
        dice.roll("10d8k=4")

    def test_interpret_successes(self):
        dice.roll("6d10?>5")
        dice.roll("10d8?<3")
        dice.roll("8d4?=3")
        dice.roll("10d4?>=3")
        dice.roll("10d4?<=3")
        dice.roll("repeat(3d6, 10)?>=4")
        dice.roll("(10d4?=3)+10d6")
        dice.roll("((10d4?=(1d4!))+10)d6")
        dice.roll("10d6?~=1")

    def test_count_pass_fail(self):
        self.assertFirstRollEquals("7d2?>0", 7)
        self.assertFirstRollEquals("7d2?>=0", 7)
        self.assertFirstRollEquals("7d2?<0", 0)
        self.assertFirstRollEquals("7d2?<=0", 0)
        self.assertFirstRollEquals("7d2?=0", 0)
        self.assertFirstRollEquals("7d2?~=0", 7)
        self.assertFirstRollEquals("7d2?h3", 3)
        self.assertFirstRollEquals("7d2?l4", 4)

    def test_interpret_explode(self):
        dice.roll("10d20!")
        dice.roll("10d4pl2!")
        dice.roll("8d6!>4")
        dice.roll("8d6!<(3d2)")
        dice.roll("8d6!<=1d4")
        dice.roll("8d10!>=4")
        dice.roll("2d4!~=3")

    def test_interpret_repeat(self):
        dice.roll("repeat(1, 3)")
        dice.roll("repeat(4d6kh3, 6)")
        dice.roll("repeat(3d6, 5)pl2")
        dice.roll("repeat(10d20-5d6, 10)kh3")
        dice.roll("repeat(5d20kh3+sqrt(4*8), 10)")
        dice.roll("repeat(repeat(4*3d8, 2), 3)")
        dice.roll("repeat(3d10, repeat(d8, 4)kh1)pl1")

    def test_interpret_aggregate(self):
        dice.roll("agg(10d6, +)")
        dice.roll("agg(10d4, -)")
        dice.roll("agg(repeat(3d10, 4), *)")
        dice.roll("agg(8d6, /)")
        dice.roll("agg(3d10, ^)")
        dice.roll("agg(4d10, %)")

    def test_braces(self):
        dice.roll("{1, 2, 3, 4}")
        dice.roll("{}")
        dice.roll("{3d10}")
        dice.roll("{2d3, 3d4}")
        self.assertFirstRollEquals("{5, 10}kh1", 10)
        self.assertFirstRollEquals("{100, 30}?=30", 1)
        self.assertFirstRollEquals("{2, 4, 6, 3}?even", 3)
        self.assertFirstRollEquals("{2, 4, 6, 3}?odd", 1)
        self.assertFirstRollEquals("{2, 4, 6, 3}keven", 12)
        self.assertFirstRollEquals("{2, 4, 6, 3}podd", 12)

    def test_explode_once(self):
        dice.roll("10d3!")
        dice.roll("10d3!o")
        dice.roll("10d3!o=2")
        self.assertFirstRollEquals("3d1!o", 6)
        self.assertFirstRollEquals("3d1!o>1", 3)

    def test_floor_ceil(self):
        self.assertFirstRollEquals("floor(10/3)", 3)
        self.assertFirstRollEquals("ceil(10/3)", 4)

    def test_interpret_explode_once(self):
        dice.roll("10d4!o")
        dice.roll("6d8!o<4")

    def test_interpret_reroll(self):
        dice.roll("5d4r=4")
        dice.roll("10d4kh2rr=3")

    def test_interpret_special(self):
        dice.roll("20dc")
        dice.roll("10dF")

    def test_interpret_label(self):
        dice.roll("2d6 [slashing] + 1d4 [bonus damage]")
        dice.roll("repeat(4d6kh3, 6) # roll for stats!")
        dice.roll("(10d3+2)[fire] - 3d10[ice] # comment")

    def test_interpret_index(self):
        dice.roll("10d6k@3")
        dice.roll("{3, 2, 1}?@0")


class HelpExamplesTest(unittest.TestCase):
    def test_interpret_examples(self):
        dice.roll("4d6?=5")
        dice.roll("4d6kh3")
        dice.roll("repeat(3d6, 5)pl2")
        dice.roll("8d6rl1")
        dice.roll("2d6rr<3")
        dice.roll("10d4!")
        dice.roll("8d6!>4")
        dice.roll("3d8!o=3")
        dice.roll("1d20+5 >= 15")
        dice.roll("agg(3d8, *)")
        dice.roll("agg(repeat(3d6+2, 4), +)")
        dice.roll("1d20+5; 2d6+5")


class SetTest(unittest.TestCase):
    def setUp(self):
        self.values = [10, 5, 3, 7, -5, 0, 6]
        self.setr = dice_details.SetResult(self.values)

    def test_create_set(self):
        self.assertEqual(self.setr.get_remaining_count(), len(self.values))
        set_items = self.setr.get_all_items()
        self.assertListEqual(set_items, self.values)
        self.assertEqual(self.setr.total(), 26)

    def test_select_low_high(self):
        select_zero = dice_details._select_low_high(self.setr, 0, high=False)
        self.assertEqual(len(select_zero), 0)

        n = 2
        select_lowest = dice_details._select_low_high(self.setr, n, high=False)
        self.assertEqual(len(select_lowest), n)
        self.assertIn(4, select_lowest)
        self.assertIn(5, select_lowest)
        self.assertNotIn(0, select_lowest)

        select_highest = dice_details._select_low_high(self.setr, n, high=True)
        self.assertEqual(len(select_highest), n)
        self.assertIn(0, select_highest)
        self.assertIn(3, select_highest)
        self.assertNotIn(4, select_highest)

    def test_select_conditional(self):
        def gt_zero_condition(value):
            return value > 0

        select_gt_zero = dice_details._select_conditional(self.setr, gt_zero_condition)
        self.assertEqual(len(select_gt_zero), 5)
        self.assertNotIn(4, select_gt_zero)
        self.assertNotIn(5, select_gt_zero)
        self.assertIn(2, select_gt_zero)

    def test_explode(self):
        # simulated 4d6
        die_size = 6
        my_dice = dice_details.DiceValues(die_size, [1, 1, 3, 6])
        exploded = dice_details.dice_reroll(
            my_dice, dice_details.ConditionalSelector(lambda x: x >= die_size)
        )
        self.assertGreater(
            exploded.get_remaining_count(), my_dice.get_remaining_count()
        )
        self.assertEqual(my_dice.get_value(), 11)
        self.assertGreater(exploded.get_value(), 11)  # type: ignore

    def test_select_index(self):
        select_index_two = dice_details.IndexSelector(2).apply(self.setr)
        self.assertEqual(len(select_index_two), 1)
        self.assertEqual(self.values[select_index_two[0]], 3)

        self.setr.drop_indices([0, 1])
        select_after_drop = dice_details.IndexSelector(2).apply(self.setr)
        self.assertEqual(len(select_after_drop), 1)
        self.assertEqual(self.values[select_after_drop[0]], -5)


class MacroTest(RollTest):
    def setUp(self) -> None:
        self.my_pi = 3.14159
        dice.GLOBAL_MACROS.add_macro("$pi", str(self.my_pi))

    def test_constant_macro(self):
        self.assertFirstRollEquals("$pi", self.my_pi)
        self.assertFirstRollEquals("$pi + $pi", self.my_pi + self.my_pi)

    def test_interpret_stats(self):
        self.assertIsNotNone(dice.GLOBAL_MACROS.get_macro_content("$stats"))
        dice.roll("$stats")
        dice.roll("{$stats, $stats}[twice, for fun]")


if __name__ == "__main__":
    unittest.main()
