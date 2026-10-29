"""Confronto semantico di versioni e lettura della versione locale.

Stdlib-only: testabile con pytest senza GUI né rete.
"""
import re
from pathlib import Path


def leggi_versione_locale(root=None):
    """Legge version.txt dalla root del progetto (default: parent del pacchetto)."""
    if root is None:
        root = Path(__file__).resolve().parent.parent
    try:
        return (root / "version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None


def parse_versione(v):
    """'v1.2.3' / '1.2.3' -> (1, 2, 3). Ritorna None se non valida."""
    if not v:
        return None
    m = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", v.strip())
    if not m:
        return None
    return tuple(int(g) if g else 0 for g in m.groups())


def confronta_versioni(remota, locale):
    """Ritorna True se `remota` è strettamente più recente di `locale`."""
    v_remota = parse_versione(remota)
    v_locale = parse_versione(locale)
    if v_remota is None or v_locale is None:
        return False
    return v_remota > v_locale
