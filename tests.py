import unittest
import asyncio
from tools import extract_urls, execute_python
import pandas as pd

class TestDataAnalystBot(unittest.TestCase):
    def test_extract_urls(self):
        text = "Here is the data: https://example.com/data.csv and https://mospi.gov.in/data.zip"
        urls = extract_urls(text)
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "https://example.com/data.csv")

    def test_execute_python_success(self):
        df_dict = {"data.csv": pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})}
        code = """
df = dfs['data.csv']
result_data = int(df['A'].sum())
"""
        success, stdout, result = execute_python(code, df_dict)
        self.assertTrue(success)
        self.assertEqual(result, 6)

    def test_execute_python_inline_csv(self):
        code = """
import io
csv_data = '''id,value
1,10
2,20'''
df = pd.read_csv(io.StringIO(csv_data))
result_data = df['value'].mean()
"""
        success, stdout, result = execute_python(code, {})
        self.assertTrue(success)
        self.assertEqual(result, 15.0)

    def test_execute_python_error_handling(self):
        code = """
result_data = dfs['non_existent.csv']['column'].mean()
"""
        success, stdout, result = execute_python(code, {})
        self.assertFalse(success)
        self.assertIn("KeyError", stdout)

if __name__ == '__main__':
    unittest.main()