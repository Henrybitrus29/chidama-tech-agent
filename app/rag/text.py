"""Tokenizing and light stemming, shared by chunk indexing and query processing."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    """a an the and or but if then than so of to in on at by for with from as into about over under
    is are was were be been being am do does did done have has had having can could should would will may might must shall
    i me my mine we us our ours you your yours he him his she her hers it its they them their theirs this that these those
    what which who whom whose when where why how there here not no yes any some all each every both few more most other
    such only own same very just also too up down out off again further once get got please tell want need know let like
    much many ok okay hi hello hey thanks thank
    itself himself herself themselves myself yourself instead offer provide company business""".split()
)

_WORD = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    """Lowercase and strip accents so 'Ñ' and 'n' compare equal."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def stem(word: str) -> str:
    """A small suffix stripper. It only needs to be consistent between documents and queries."""
    w = word
    if len(w) > 3 and not w.isdigit():
        if w.endswith("ies") and len(w) > 4:
            w = w[:-3] + "y"
        elif w.endswith("sses"):
            w = w[:-2]
        elif w.endswith("ing") and len(w) > 5:
            w = w[:-3]
        elif w.endswith("ed") and len(w) > 4:
            w = w[:-2]
        elif w.endswith(("ches", "shes", "xes", "zes")):
            w = w[:-2]
        elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        if w.endswith("e") and len(w) > 4:
            w = w[:-1]
    return w


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    out: list[str] = []
    for w in _WORD.findall(fold(text)):
        if not keep_stopwords and (w in STOPWORDS or (len(w) < 2 and not w.isdigit())):
            continue
        out.append(stem(w))
    return out
