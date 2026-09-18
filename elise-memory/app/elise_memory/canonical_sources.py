"""Explicit canonical source coordinates.

No Drive discovery is performed at runtime: only these approved workbook/sheet
coordinates may feed the compiler.
"""
from .google_sheets import SheetRange

CANONICAL_RANGES = {
    "metier": SheetRange(
        "16D6ce8my4_mAkCDJKn2z4v2sVWmGbJZkLDP0w2pKxIo",
        "Référentiel métier", "A1:P1000"),
    "memory_ia": SheetRange(
        "16D6ce8my4_mAkCDJKn2z4v2sVWmGbJZkLDP0w2pKxIo",
        "Mémoire IA", "A1:T1000"),
    "relations": SheetRange(
        "1Q5-X_popgmdeY26joNvGnNmA1msrYFGN-iKlub6HMXk",
        "09_Relations fonctionnelles", "A1:O1000"),
    "automations": SheetRange(
        "1UZ6pI3ToIXSt28is1h_SrYY_0XXnNtbn_5aoXnbWm3c",
        "Automatisations", "A1:M500"),
    "scripts": SheetRange(
        "1tgfhLH3YZjebu-h_7zSyNG-p7923NDZQMipwE5mAT-A",
        "Scripts Pyscript", "A1:Q500"),
}
