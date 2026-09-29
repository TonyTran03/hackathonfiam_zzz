"""Company names, rendered the way the rules ask for them.

The panel stores CRSP's own style: acronyms spelled out letter by letter
("C M E GROUP INC"), the state of incorporation appended ("3 D SYSTEMS CORP
DEL"), and share-class history kept in the name ("LIBERTY MEDIA CORP 3RD NEW").
The rules ask for "NVDA, NVIDIA Corporation", so the letters are rejoined, the
registration suffixes dropped and the rest title-cased.

This reformats only. Nothing is looked up, and no later name is substituted for
an earlier one -- the rules warn against exactly that. The deck's JavaScript
carries the same rules so a chart label and a table row cannot disagree.
"""
import re

KEEP_UPPER = {"USA", "US", "PLC", "NV", "SA", "AG", "LP", "LLC", "AB", "ASA",
              "II", "III", "IV", "REIT", "ETF"}
SMALL = {"OF", "AND", "THE", "FOR", "DE"}
MARK = "\x01"

_SUFFIX = re.compile(r"\s+(?:3RD|2ND|1ST)\s+NEW$|\s+NEW$|\s+DEL$")
# A run of single characters, optionally joined by "&": "C M E", "P G & E", "3 D".
_ACRONYM = re.compile(r"\b[A-Z0-9](?:\s*&?\s*\b[A-Z0-9]\b){1,4}")
_EXPAND = [(r"\bHldgs\b", "Holdings"), (r"\bGrp\b", "Group"),
           (r"\bIntl\b", "International"), (r"\bTechs\b", "Technologies"),
           (r"\bCos\b", "Companies"), (r"\bMfg\b", "Manufacturing"),
           # Capitalisation and hyphens that cannot be inferred from CRSP's
           # all-caps spelling. The deck's JavaScript carries the same pair.
           (r"\bMaxlinear\b", "MaxLinear"), (r"\bD Wave\b", "D-Wave")]


def pretty_name(raw):
    if raw is None or (isinstance(raw, float) and raw != raw):
        return ""
    t = str(raw).strip().upper()
    if not t:
        return ""
    t = _SUFFIX.sub("", t)

    def join(m):
        j = re.sub(r"\s+", "", m.group(0))
        return MARK + j + MARK if len(j) <= 5 else m.group(0)

    t = _ACRONYM.sub(join, t)
    t = re.sub(r"\s+&\s+", " & ", t)

    out = []
    for i, w in enumerate(t.split()):
        if MARK in w:
            out.append(w.replace(MARK, ""))
        elif re.sub(r"[^A-Z0-9&.]", "", w) in KEEP_UPPER:
            out.append(w)
        elif i > 0 and w in SMALL:
            out.append(w.lower())
        else:
            out.append(w[0] + w[1:].lower())
    s = " ".join(out)
    for pat, rep in _EXPAND:
        s = re.sub(pat, rep, s)
    return s
