import unittest
import pandas as pd
from scripts.prescreen import select_history_pool

class PrescreenTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame([{
            "code": str(i).zfill(6), "name": f"测试{i}",
            "price": 10., "amount": (20 + i%40) * 1000000.,
            "change_pct": (-3.0 if i%3==0 else 4.0 if i%3==1 else .7),
            "volume_ratio": 1.2 + i%5,
            "industry": "测试"
        } for i in range(1,501)])

    def test_covers_decliners_and_risers(self):
        x=select_history_pool(self.sample(), 60)
        counts=x.attrs["selection"]["bucket_counts"]
        self.assertEqual(len(x),60)
        self.assertGreaterEqual(counts["decliners"],15)
        self.assertGreaterEqual(counts["risers"],15)
        self.assertEqual(len(set(x.code)),len(x.code))
        self.assertTrue(x["change_pct"].lt(0).any())
        self.assertTrue(x["change_pct"].gt(0).any())

    def test_deterministic_order(self):
        df=self.sample()
        result=select_history_pool(df,42)
        again=select_history_pool(df.sample(frac=1,random_state=3),42)
        self.assertEqual(result.code.tolist(),again.code.tolist())

    def test_filters_st_and_no_liquidity(self):
        df=self.sample()
        df.loc[0,"name"]="*ST测试"
        df.loc[1,"amount"]=0
        x=select_history_pool(df,120)
        self.assertNotIn(str(df.loc[0,"code"]).zfill(6),x.code.values)
        self.assertNotIn(str(df.loc[1,"code"]).zfill(6),x.code.values)

    def test_empty_or_invalid(self):
        df=self.sample()
        with self.assertRaises(ValueError):
            select_history_pool(df,121)
        df["amount"]=0
        with self.assertRaises(RuntimeError):
            select_history_pool(df,30)

if __name__=="__main__":
    unittest.main()
