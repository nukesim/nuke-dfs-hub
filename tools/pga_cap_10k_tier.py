from pathlib import Path

portfolio = Path("nuke_pga_portfolio.py")
s = portfolio.read_text()
old = '''def salary_build_type(salaries):\n    """$9,000 through $9,999 is tier 9, regardless of exact salary."""\n    values = np.asarray(salaries, dtype=float)\n    if len(values) != 6 or not np.isfinite(values).all() or np.any(values < 1000):\n        raise PortfolioError("A salary build needs six valid golfer salaries.")\n    return "/".join(map(str, sorted((values//1000).astype(int), reverse=True)))\n'''
new = '''def salary_build_type(salaries):\n    """Salary-build tiers top out at 10; every golfer priced $10,000+ is a 10K golfer."""\n    values = np.asarray(salaries, dtype=float)\n    if len(values) != 6 or not np.isfinite(values).all() or np.any(values < 1000):\n        raise PortfolioError("A salary build needs six valid golfer salaries.")\n    tiers = np.minimum((values//1000).astype(int), 10)\n    return "/".join(map(str, sorted(tiers, reverse=True)))\n'''
if old not in s:
    if new not in s:
        raise RuntimeError("Could not find salary_build_type block to update")
else:
    s = s.replace(old, new, 1)
portfolio.write_text(s)

# Invalidate any already-rendered PGA portfolio rows that contain old 11K labels.
page = Path("pages/15_PGA_SIM.py")
p = page.read_text()
if "PGA_PORTFOLIO_VERSION=5" in p:
    p = p.replace("PGA_PORTFOLIO_VERSION=5", "PGA_PORTFOLIO_VERSION=6", 1)
elif "PGA_PORTFOLIO_VERSION=6" not in p:
    raise RuntimeError("Unexpected PGA portfolio version")
page.write_text(p)

# Keep the regression helper aligned with the prior removal of DK FPPG.
test = Path("tests/test_pga_portfolio.py")
t = test.read_text()
t = t.replace('"base_projection"', '"salary_baseline"')

# Update the older salary-band expectation to the new 10K ceiling.
t = t.replace(
    'self.assertEqual(salary_build_type([11000,9000,8000,7000,6000,5000]), "11/9/8/7/6/5")',
    'self.assertEqual(salary_build_type([11000,9000,8000,7000,6000,5000]), "10/9/8/7/6/5")',
)

# Add a permanent regression test for the 10K ceiling if it is not already present.
marker = "def test_salary_build_type_caps_10k_and_above"
if marker not in t:
    needle = "class PGAPortfolioTests(unittest.TestCase):\n"
    if needle not in t:
        raise RuntimeError("Could not find PGAPortfolioTests class")
    addition = '''class PGAPortfolioTests(unittest.TestCase):\n    def test_salary_build_type_caps_10k_and_above(self):\n        self.assertEqual(salary_build_type([11000, 10700, 9900, 8800, 7500, 6100]), "10/10/9/8/7/6")\n        self.assertEqual(salary_build_type([12500, 10000, 9999, 9000, 8000, 7000]), "10/10/9/9/8/7")\n\n'''
    t = t.replace(needle, addition, 1)
test.write_text(t)
