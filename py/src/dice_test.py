import dice
import unittest


class DiceTest(unittest.TestCase):

    def assertFirstRollEquals(self, roll_input, expected):
        results = dice.roll(roll_input)
        self.assertAlmostEqual(results[0].get_value(), expected)

    def assertFormattingEquals(self, roll_input, expected):
        results = dice.roll(roll_input)
        self.assertEqual(dice.format_roll_results(results), expected)

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

    def test_interpret_diceroll(self):
        dice.roll("d10")
        dice.roll("3d20")
        dice.roll("8d6")
        dice.roll("10C4d3")
        dice.roll("(10C4)d3")
        dice.roll("10 + (-10)d4")
        dice.roll("3d((2+23)/5)")

    def test_interpret_dropkeep(self):
        dice.roll("4d6kh3")
        dice.roll("8d12dl3")
        dice.roll("30d10dl1kh5dl2")

    def test_interpret_explode(self):
        dice.roll("10d20!")
        dice.roll("10d4dl2!")

    def test_interpret_repeat(self):
        dice.roll("repeat(1, 3)")
        dice.roll("repeat(4d6kh3, 6)")
        dice.roll("repeat(3d6, 5)dl2")
        dice.roll("repeat(10d20-5d6, 10)kh3")
        dice.roll("repeat(5d20kh3+sqrt(4*8), 10)")
        dice.roll("repeat(repeat(4*3d8, 2), 3)")

    # Test that semicolons separate an input into multiple rolls.
    def test_breaks(self):
        results = dice.roll("1d20+5; 2d6+5")
        self.assertEqual(len(results), 2)
        results = dice.roll("1+5d2;(2d9)*3;15")
        self.assertEqual(len(results), 3)

if __name__ == '__main__':
    unittest.main()
