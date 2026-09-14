import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from verify_beta import parse_prices,beta


class BetaTests(unittest.TestCase):
    def test_rejects_date_mismatch_and_silent_row_loss(self):
        for text in ["01/02/24 $ 10.00 01/03/24 $ 100.00", "01/02/24 missing 01/02/24 $ 100.00"]:
            with self.assertRaises(ValueError): parse_prices(text)

    def test_slope_uses_returns_instead_of_price_levels(self):
        # Market returns +10%, -10%; stock returns +20%, -20% -> beta 2.
        rows=parse_prices("01/02/24 $ 10.00 01/02/24 $ 100.00\n"
                          "01/03/24 $ 12.00 01/03/24 $ 110.00\n"
                          "01/04/24 $ 9.60 01/04/24 $ 99.00")
        self.assertAlmostEqual(beta(rows),2.0)


if __name__ == "__main__": unittest.main()
