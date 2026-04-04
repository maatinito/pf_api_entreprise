#!/usr/bin/env python3
"""
Extrait la table de correspondance code_commune -> {communeAssociee, communeMere}
depuis l'ancien serveur i-taiete.

Pour chaque code commune unique trouvé dans le CSV, interroge i-taiete avec
plusieurs numéros TAHITI exemple (--per-commune, défaut 2) jusqu'à trouver
la commune dans la réponse.

Sauvegarde le résultat dans reference_data/communes.json.

Usage:
  python3 benchmark/extract_communes.py
  python3 benchmark/extract_communes.py --csv exportrte.csv --output reference_data/communes.json
  python3 benchmark/extract_communes.py --per-commune 3  # essaie 3 TAHITIs par commune
"""

import argparse
import base64
import csv
import json
import sys
import time
import urllib.request
import urllib.error

# --- Config ancien serveur ---
OLD_BASE_URL = "https://api.gov.pf/i-taiete"
OLD_USER = "MES-DEMARCHES"
OLD_PASSWORD = "84b5b7f1-ec3c-4aa4-8bd9-74c9802233a9"
OLD_API_KEY = "5df5bc28-b64c-4dee-a34c-cd0dc63172bc"


def extract_commune_tahiti_mapping(csv_path, per_commune):
    """
    Parse le CSV et construit un mapping code_commune -> [numtah1, numtah2, ...].
    Conserve jusqu'à `per_commune` numéros TAHITI différents par code commune.
    Utilise les colonnes Com_ETAB (col 12) et Com_BP_ENT (col 8).
    """
    commune_to_tahitis = {}
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        if not header:
            print("ERREUR: CSV vide")
            sys.exit(1)
        for row in reader:
            if len(row) < 34:
                continue
            numtah = row[0].strip()
            if not numtah:
                continue
            for col in [12, 8]:
                code = row[col].strip()
                if not code:
                    continue
                tahitis = commune_to_tahitis.setdefault(code, [])
                if numtah not in tahitis and len(tahitis) < per_commune:
                    tahitis.append(numtah)
    return commune_to_tahitis


def call_old_server(numero_tahiti):
    """Appelle l'ancien serveur i-taiete."""
    url = f"{OLD_BASE_URL}/etablissements/Entreprise?numeroTahiti={numero_tahiti}"
    credentials = base64.b64encode(f"{OLD_USER}:{OLD_PASSWORD}".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {credentials}",
        "X-Gravitee-Api-Key": OLD_API_KEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:
        return {"_error": str(e)}


def extract_commune_from_response(data, target_code):
    """
    Extrait communeAssociee et communeMere depuis la réponse i-taiete
    pour un code commune donné (via champImport).
    Cherche dans communeGeo et entreprise.commune.
    """
    if not isinstance(data, list):
        return None

    target_int = int(target_code) if target_code.isdigit() else 0

    for etab in data:
        if not isinstance(etab, dict):
            continue
        # Chercher dans communeGeo
        commune_geo = etab.get("communeGeo")
        if isinstance(commune_geo, dict) and commune_geo.get("champImport") == target_int:
            assoc = commune_geo.get("communeAssociee", "")
            mere = commune_geo.get("communeMere", "")
            if assoc:
                return {"communeAssociee": assoc, "communeMere": mere}
        # Chercher dans entreprise.commune
        entreprise = etab.get("entreprise")
        if isinstance(entreprise, dict):
            commune_ent = entreprise.get("commune")
            if isinstance(commune_ent, dict) and commune_ent.get("champImport") == target_int:
                assoc = commune_ent.get("communeAssociee", "")
                mere = commune_ent.get("communeMere", "")
                if assoc:
                    return {"communeAssociee": assoc, "communeMere": mere}
    return None


def main():
    parser = argparse.ArgumentParser(description="Extraction des communes depuis i-taiete")
    parser.add_argument("--csv", default="exportrte.csv", help="Chemin vers exportrte.csv")
    parser.add_argument("--output", default="reference_data/communes.json", help="Fichier de sortie")
    parser.add_argument("--per-commune", type=int, default=2,
                        help="Nombre de TAHITIs à essayer par commune (défaut: 2)")
    args = parser.parse_args()

    print(f"Lecture du CSV {args.csv} (jusqu'à {args.per_commune} TAHITIs par commune)...")
    commune_to_tahitis = extract_commune_tahiti_mapping(args.csv, args.per_commune)
    print(f"{len(commune_to_tahitis)} codes communes uniques trouvés.")

    communes = {}
    errors = []
    total = len(commune_to_tahitis)

    for i, (code, tahitis) in enumerate(sorted(commune_to_tahitis.items())):
        print(f"  [{i+1}/{total}] Code {code}...", end=" ", flush=True)

        found = False
        for tahiti in tahitis:
            data = call_old_server(tahiti)

            if isinstance(data, dict) and "_error" in data:
                print(f"ERREUR (TAHITI {tahiti}): {data['_error']}")
                errors.append((code, tahiti, data["_error"]))
                time.sleep(0.5)
                continue

            result = extract_commune_from_response(data, code)
            if result:
                communes[code] = result
                print(f"OK via {tahiti}: {result['communeAssociee']} / {result['communeMere']}")
                found = True
                break

            time.sleep(0.2)

        if not found and not any(e[0] == code for e in errors):
            print(f"NON TROUVE (essayé: {tahitis})")
            errors.append((code, tahitis, "commune non trouvée dans aucune réponse"))

        time.sleep(0.2)

    # Sauvegarder
    sorted_communes = dict(sorted(communes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sorted_communes, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Résultat: {len(communes)}/{total} communes extraites, {len(errors)} erreurs")
    print(f"Sauvegardé dans {args.output}")

    if errors:
        print(f"\nCommunes non trouvées:")
        for code, tahitis, err in errors:
            print(f"  Code {code} (TAHITI {tahitis}): {err}")


if __name__ == "__main__":
    main()
