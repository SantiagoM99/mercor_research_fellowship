import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_followup_sources import advertising,nps


class SourceTests(unittest.TestCase):
    def test_campaign_ratio_uses_sums_not_mean_of_ratios(self):
        rows=[{'Payment_Method':'Fixed Price','Payment ($)':'10',' Total_Impressions ':'100'},
              {'Payment_Method':'Fixed Price','Payment ($)':'30',' Total_Impressions ':'30'},
              {'Payment_Method':'Pay Per Click','Payment ($)':'999',' Total_Impressions ':'999'}]
        self.assertEqual(advertising(rows)['value'],Decimal('3.25'))

    def test_passive_respondents_remain_in_nps_denominator(self):
        rows=[dict(Generation='Gen Z',Likelihood_to_Recommend=str(x)) for x in [9,10,6,7]]
        rows.append(dict(Generation='Boomer',Likelihood_to_Recommend='10'))
        result=nps(rows)
        self.assertEqual(result['value'],Decimal('25'))
        self.assertEqual(result['respondents'],4)


if __name__=='__main__': unittest.main()
