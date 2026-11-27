"""Build the website from src/ (run: python build.py).

src/index_template.html  page layout, styles and app code (placeholders __CORE__, __V2__, __SAMPLE__)
src/_core.js             maths: returns, covariance, portfolio risk, charts
src/_v2.js               advanced analysis: benchmark ratios, stress tests, strategies, Brinson, rebalancing, PMS fees, GIPS
src/admin.html           admin site (Firebase config filled in from the template)
Writes index.html, 404.html, one copy per page folder (real page addresses) and admin/index.html.
"""
import os
import re
import sys

R = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(R, "src")
PAGES = ["plan", "portfolio", "perf", "pair", "single", "screen", "learn", "mine"]


def sample_block():
    """Keep the small offline sample data that is already inside the built index.html."""
    old = open(os.path.join(R, "index.html"), encoding="utf-8").read()
    i = old.index("const SAMPLE=") + len("const SAMPLE=")
    depth = 0
    for j, ch in enumerate(old[i:], i):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return old[i:j + 1]
    raise ValueError("sample data not found")


def main():
    read = lambda n: open(os.path.join(S, n), encoding="utf-8").read()
    t = read("index_template.html").replace("__V2__", read("_v2.js")).replace("__CORE__", read("_core.js")).replace("__SAMPLE__", sample_block())
    for path in ["index.html", "404.html"] + [os.path.join(p, "index.html") for p in PAGES]:
        os.makedirs(os.path.dirname(os.path.join(R, path)) or R, exist_ok=True)
        open(os.path.join(R, path), "w", encoding="utf-8").write(t)
    cfg = re.search(r"const FBCFG=(\{.*?\});", t).group(1)
    os.makedirs(os.path.join(R, "admin"), exist_ok=True)
    open(os.path.join(R, "admin", "index.html"), "w", encoding="utf-8").write(read("admin.html").replace("__FBCFG__", cfg))
    if "--debug" in sys.argv:  # test copy with a few internals exposed (not committed)
        k = t.rindex("bindAuth();bindName();boot();fbInit();")
        open(os.path.join(R, "test_dbg.html"), "w", encoding="utf-8").write(
            t[:k] + "window.__dbg={get X(){return lastExport},get S(){return state},monteCarlo};\n" + t[k:])
    print("built", len(t), "bytes")


if __name__ == "__main__":
    main()
