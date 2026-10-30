"""CER metric."""
from khojki import cer


def test_cer_rules():
    cer.demo()


def test_cer_matches_an_independent_implementation():
    """Second route (verifying-output): a two-row Wagner-Fischer written separately must agree."""
    def lev(a, b):
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]
    pairs = [("kitten", "sitting"), ("", "abc"), ("abc", ""), ("\U00011224\U0001122E\U0001123A", "��\U0001123A"),
             ("flaw", "lawn"), ("abcdef", "azced")]
    for a, b in pairs:
        assert cer.align(a, b)[0] == lev(a, b)
