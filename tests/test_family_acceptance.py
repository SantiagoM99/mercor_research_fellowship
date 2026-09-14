import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from family_acceptance import upper_bound,binomial_cdf,family_bound,zero_error_sample


class FamilyAcceptanceTests(unittest.TestCase):
    def test_zero_errors_and_boundaries(self):
        self.assertEqual(upper_bound(0,0),1)
        self.assertEqual(upper_bound(10,10),1)
        self.assertAlmostEqual(upper_bound(0,45),1-.05**(1/45))
        self.assertGreater(upper_bound(0,45,.05/6),.10)
        n=zero_error_sample(.02,6)
        self.assertLessEqual(upper_bound(0,n,.05/6),.02)
        self.assertGreater(upper_bound(0,n-1,.05/6),.02)

    def test_binomial_inversion_and_monotonicity(self):
        for n in (10,45):
            previous=0
            for k in range(n):
                upper=upper_bound(k,n)
                self.assertAlmostEqual(binomial_cdf(k,n,upper),.05,places=10)
                self.assertGreater(upper,previous);previous=upper

    def test_exact_coverage_on_binomial_grid(self):
        for n in (5,16,45):
            for p in (.001,.01,.02,.05,.10,.5,.99):
                failure=sum(math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1) if upper_bound(k,n)<p)
                self.assertLessEqual(failure,.05+1e-12)

    def test_repeats_do_not_change_number_of_families(self):
        a=family_bound([0,1,0],[10,10,0])
        b=family_bound([0,100,0],[1000,1000,0])
        self.assertEqual(a,b)
        self.assertEqual(a['eligible_families'],2)
        self.assertEqual(family_bound([],[])['upper_error_bound'],1)
        with self.assertRaises(ValueError): family_bound([2],[1])


if __name__=='__main__':unittest.main()
