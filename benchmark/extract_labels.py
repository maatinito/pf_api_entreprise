#!/usr/bin/env python3
"""
Extrait les libellés exacts depuis le cache i-taiete et met à jour
reference_data/naf.json et reference_data/effectifs.json.

Usage:
  python3 benchmark/extract_labels.py --cache benchmark/cache_itaiete.json
  python3 benchmark/extract_labels.py --cache benchmark/cache_itaiete.json --dry-run
"""

import argparse
import json
import os
import sys
from collections import Counter


def extract_from_cache(cache):
    """Extrait code→libelle NAF et id→libelle effectifs depuis le cache."""
    naf_labels = {}       # code → libelle
    effectif_by_id = {}   # id → libelle

    for numtah, data in cache.items():
        if not isinstance(data, list):
            continue
        for etab in data:
            if not isinstance(etab, dict):
                continue

            # NAF activitePrincipale de l'établissement
            ap = etab.get("activitePrincipale")
            if isinstance(ap, dict) and ap.get("code") and ap.get("libelle"):
                naf_labels[ap["code"]] = ap["libelle"]

            # NAF activiteSecondaires de l'établissement
            for as_ in etab.get("activiteSecondaires") or []:
                if isinstance(as_, dict) and as_.get("code") and as_.get("libelle"):
                    naf_labels[as_["code"]] = as_["libelle"]

            # Niveau entreprise
            ent = etab.get("entreprise") or {}

            # NAF activitePrincipale de l'entreprise
            ap_ent = ent.get("activitePrincipale")
            if isinstance(ap_ent, dict) and ap_ent.get("code") and ap_ent.get("libelle"):
                naf_labels[ap_ent["code"]] = ap_ent["libelle"]

            # classeEffectif (niveau entreprise)
            ce = ent.get("classeEffectif")
            if isinstance(ce, dict) and ce.get("id") is not None and ce.get("libelle"):
                effectif_by_id[ce["id"]] = ce["libelle"]

    return naf_labels, effectif_by_id


def update_naf(naf_current, naf_labels):
    """Met à jour les libellés NAF. Retourne (dict_mis_a_jour, nb_modifiés, nb_nouveaux)."""
    naf_out = dict(naf_current)
    updated = 0
    new = 0

    for code, libelle in naf_labels.items():
        if code in naf_out:
            if naf_out[code] != libelle:
                print(f"  NAF {code}: {naf_out[code]!r} → {libelle!r}")
                updated += 1
            naf_out[code] = libelle
        else:
            print(f"  NAF {code} (nouveau): {libelle!r}")
            naf_out[code] = libelle
            new += 1

    return dict(sorted(naf_out.items())), updated, new


def update_effectifs(effectifs_current, effectif_by_id):
    """
    Met à jour les libellés effectifs.
    Mapping i-taiete ID → code CSV :
      - ID 1-9  → code "01"-"09" (direct)
      - ID 10   → code "00" (Aucune personne — cas particulier)
    Retourne (dict_mis_a_jour, nb_modifiés).
    """
    # Mapping ID i-taiete → code effectif CSV
    EFFECTIF_ID_TO_CODE = {10: "00"}
    for i in range(1, 10):
        EFFECTIF_ID_TO_CODE[i] = f"{i:02d}"

    effectifs_out = dict(effectifs_current)
    updated = 0

    print(f"\n  IDs effectifs trouvés dans le cache: {sorted(effectif_by_id.keys())}")
    print(f"  Mapping ID→code: {EFFECTIF_ID_TO_CODE}")

    for eff_id, libelle in sorted(effectif_by_id.items()):
        code = EFFECTIF_ID_TO_CODE.get(int(eff_id))
        if code is None:
            print(f"  WARN: Effectif ID {eff_id} sans mapping connu ({libelle!r}) — ignoré")
            continue
        if code not in effectifs_out:
            print(f"  WARN: Code {code} absent de effectifs.json — ignoré")
            continue
        current = effectifs_out.get(code)
        if current != libelle:
            print(f"  Effectif {code} (ID {eff_id}): {current!r} → {libelle!r}")
            updated += 1
        effectifs_out[code] = libelle

    return effectifs_out, updated


def main():
    parser = argparse.ArgumentParser(description="Extraction labels depuis cache i-taiete")
    parser.add_argument("--cache", default="benchmark/cache_itaiete.json",
                        help="Chemin vers le cache i-taiete (défaut: benchmark/cache_itaiete.json)")
    parser.add_argument("--naf-out", default="reference_data/naf.json",
                        help="Fichier NAF à mettre à jour (défaut: reference_data/naf.json)")
    parser.add_argument("--effectifs-out", default="reference_data/effectifs.json",
                        help="Fichier effectifs à mettre à jour (défaut: reference_data/effectifs.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Afficher les changements sans modifier les fichiers")
    args = parser.parse_args()

    if not os.path.exists(args.cache):
        print(f"ERREUR: Cache introuvable: {args.cache}", file=sys.stderr)
        sys.exit(1)

    # Charger le cache
    print(f"Chargement du cache {args.cache}...")
    with open(args.cache, "r", encoding="utf-8") as f:
        cache = json.load(f)
    print(f"Cache chargé: {len(cache)} entrées.")

    # Charger les données de référence actuelles
    with open(args.naf_out, "r", encoding="utf-8") as f:
        naf_current = json.load(f)
    with open(args.effectifs_out, "r", encoding="utf-8") as f:
        effectifs_current = json.load(f)

    # Extraire les labels du cache
    print("\nExtraction des labels depuis le cache...")
    naf_labels, effectif_by_id = extract_from_cache(cache)
    print(f"  Codes NAF trouvés : {len(naf_labels)}")
    print(f"  IDs effectifs trouvés : {len(effectif_by_id)}")

    # Mise à jour NAF
    print(f"\n--- Mise à jour NAF ({args.naf_out}) ---")
    naf_out, naf_updated, naf_new = update_naf(naf_current, naf_labels)
    print(f"  Résumé NAF: {naf_updated} mis à jour, {naf_new} nouveaux")

    # Mise à jour effectifs
    print(f"\n--- Mise à jour effectifs ({args.effectifs_out}) ---")
    effectifs_out, eff_updated = update_effectifs(effectifs_current, effectif_by_id)
    print(f"  Résumé effectifs: {eff_updated} mis à jour")

    if args.dry_run:
        print("\n[DRY RUN] Aucune modification appliquée.")
        return

    # Sauvegarder NAF
    with open(args.naf_out, "w", encoding="utf-8") as f:
        json.dump(naf_out, f, ensure_ascii=False, indent=2)
    print(f"\nSauvegardé: {args.naf_out}")

    # Sauvegarder effectifs
    with open(args.effectifs_out, "w", encoding="utf-8") as f:
        json.dump(effectifs_out, f, ensure_ascii=False, indent=2)
    print(f"Sauvegardé: {args.effectifs_out}")


if __name__ == "__main__":
    main()
