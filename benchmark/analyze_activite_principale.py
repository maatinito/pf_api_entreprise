#!/usr/bin/env python3
"""
Analyse pourquoi ~39% des entreprises ont activitePrincipale=null dans i-taiete
alors que le CSV contient un code NAF.

Usage:
  python3 benchmark/analyze_activite_principale.py --cache benchmark/cache_itaiete.json
  python3 benchmark/analyze_activite_principale.py --cache benchmark/cache_itaiete.json --csv exportrte.csv
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict


def load_csv_codes(csv_path):
    """Charge les codes NAF depuis le CSV (colonne APE_ENT = col 28 environ)."""
    csv_codes = {}  # numtah → code_naf_csv
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        if header:
            # Chercher les colonnes pertinentes
            cols = {h.strip().upper(): i for i, h in enumerate(header)}
            print(f"Colonnes CSV disponibles (extrait): {list(cols.items())[:10]}")
        for row in reader:
            if not row or not row[0].strip():
                continue
            numtah = row[0].strip()
            if numtah not in csv_codes and len(row) > 5:
                # Essayer plusieurs colonnes potentielles pour le code APE/NAF entreprise
                ape = None
                for col_name in ["APE_ENT", "CODEAPE", "CODE_APE", "NAF", "APE"]:
                    if col_name in cols and cols[col_name] < len(row):
                        val = row[cols[col_name]].strip()
                        if val:
                            ape = val
                            break
                csv_codes[numtah] = ape
    return csv_codes


def main():
    parser = argparse.ArgumentParser(
        description="Analyse activitePrincipale null dans i-taiete"
    )
    parser.add_argument("--cache", default="benchmark/cache_itaiete.json")
    parser.add_argument("--csv", default=None, help="Chemin exportrte.csv pour croiser avec les codes CSV")
    parser.add_argument("--top", type=int, default=15, help="Nombre de formes juridiques à afficher (défaut: 15)")
    args = parser.parse_args()

    print(f"Chargement du cache {args.cache}...")
    with open(args.cache, "r", encoding="utf-8") as f:
        cache = json.load(f)
    print(f"Cache chargé: {len(cache)} entrées.")

    csv_codes = {}
    if args.csv:
        print(f"Chargement CSV {args.csv}...")
        csv_codes = load_csv_codes(args.csv)
        print(f"Codes CSV chargés: {len(csv_codes)} entreprises.")

    # Stats globales
    total = 0
    ap_null = 0
    ap_not_null = 0

    # Répartition par forme juridique
    fj_null = Counter()       # forme juridique code → nb AP null
    fj_not_null = Counter()   # forme juridique code → nb AP non-null

    # Répartition par présence de code dans le CSV
    csv_has_code_but_itaiete_null = 0
    csv_no_code_itaiete_null = 0

    # Codes NAF retournés par i-taiete (quand non-null)
    naf_codes_itaiete = Counter()

    for numtah, data in cache.items():
        if not isinstance(data, list) or not data:
            continue
        first = data[0]
        if not isinstance(first, dict):
            continue
        ent = first.get("entreprise")
        if not isinstance(ent, dict):
            continue

        total += 1
        ap = ent.get("activitePrincipale")
        fj = ent.get("formeJuridique") or {}
        fj_code = fj.get("code") if isinstance(fj, dict) else None

        if ap is None:
            ap_null += 1
            fj_null[fj_code] += 1
            if csv_codes:
                csv_code = csv_codes.get(numtah)
                if csv_code:
                    csv_has_code_but_itaiete_null += 1
                else:
                    csv_no_code_itaiete_null += 1
        else:
            ap_not_null += 1
            fj_not_null[fj_code] += 1
            if isinstance(ap, dict) and ap.get("code"):
                naf_codes_itaiete[ap["code"]] += 1

    # Affichage
    print(f"\n{'='*70}")
    print(f" ANALYSE activitePrincipale entreprise — cache i-taiete")
    print(f"{'='*70}")
    print(f" Total entreprises analysées : {total}")
    if total > 0:
        print(f" AP non-null                 : {ap_not_null:>7} ({ap_not_null/total*100:.1f}%)")
        print(f" AP null                     : {ap_null:>7} ({ap_null/total*100:.1f}%)")

    if csv_codes and ap_null > 0:
        print(f"\n Croisement avec CSV (pour AP=null dans i-taiete):")
        print(f"   CSV a un code NAF         : {csv_has_code_but_itaiete_null} ({csv_has_code_but_itaiete_null/ap_null*100:.1f}%)")
        print(f"   CSV sans code NAF         : {csv_no_code_itaiete_null} ({csv_no_code_itaiete_null/ap_null*100:.1f}%)")

    # Taux AP=null par forme juridique
    all_fj = set(fj_null.keys()) | set(fj_not_null.keys())
    fj_data = []
    for code in all_fj:
        n = fj_null.get(code, 0)
        p = fj_not_null.get(code, 0)
        tot = n + p
        fj_data.append((code, tot, n, p))
    fj_data.sort(key=lambda x: -x[1])

    print(f"\n Taux AP=null par forme juridique (top {args.top} par volume):")
    print(f"  {'FJ':<10} {'Total':>8} {'AP null':>8} {'AP ok':>8} {'%null':>7}")
    print(f"  {'─'*10} {'─'*8} {'─'*8} {'─'*8} {'─'*7}")
    for code, tot, n, p in fj_data[:args.top]:
        pct = n / tot * 100 if tot > 0 else 0
        print(f"  {str(code or 'None'):<10} {tot:>8} {n:>8} {p:>8} {pct:>6.1f}%")

    # Top codes NAF i-taiete (quand non-null)
    print(f"\n Top 10 codes NAF retournés par i-taiete (AP≠null):")
    for code, cnt in naf_codes_itaiete.most_common(10):
        print(f"   {code:<10} {cnt:>6}")

    # Formes juridiques avec 100% AP=null
    fj_toujours_null = [(c, t, n, p) for c, t, n, p in fj_data if n == t and t >= 10]
    if fj_toujours_null:
        print(f"\n Formes juridiques avec 100% AP=null (≥10 entreprises):")
        for code, tot, n, p in sorted(fj_toujours_null, key=lambda x: -x[1]):
            print(f"   FJ {str(code or 'None'):<10} — {tot} entreprises")

    # Formes juridiques avec 0% AP=null
    fj_jamais_null = [(c, t, n, p) for c, t, n, p in fj_data if n == 0 and t >= 10]
    if fj_jamais_null:
        print(f"\n Formes juridiques avec 0% AP=null (≥10 entreprises):")
        for code, tot, n, p in sorted(fj_jamais_null, key=lambda x: -x[1]):
            print(f"   FJ {str(code or 'None'):<10} — {tot} entreprises")


if __name__ == "__main__":
    main()
