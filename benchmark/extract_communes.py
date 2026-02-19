#!/usr/bin/env python3
"""
Extrait la table de correspondance code_commune -> {communeAssociee, communeMere}
depuis l'ancien serveur i-taiete.

Pour chaque code commune unique trouvé dans le CSV, interroge i-taiete avec un
numéro TAHITI exemple et extrait les noms de commune de la réponse JSON.

Sauvegarde le résultat dans reference_data/communes.json.

Usage:
  python3 benchmark/extract_communes.py
  python3 benchmark/extract_communes.py --csv exportrte.csv --output reference_data/communes.json
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


def extract_commune_tahiti_mapping(csv_path):
    """
    Parse le CSV et construit un mapping code_commune -> numéro TAHITI exemple.
    Utilise les colonnes Com_ETAB (col 12) et Com_BP_ENT (col 8).
    """
    commune_to_tahiti = {}
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
            # Col 12: Com_ETAB
            code_etab = row[12].strip()
            if code_etab and code_etab not in commune_to_tahiti:
                commune_to_tahiti[code_etab] = numtah
            # Col 8: Com_BP_ENT
            code_bp = row[8].strip()
            if code_bp and code_bp not in commune_to_tahiti:
                commune_to_tahiti[code_bp] = numtah
    return commune_to_tahiti


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

    for etab in data:
        if not isinstance(etab, dict):
            continue
        # Chercher dans communeGeo
        commune_geo = etab.get("communeGeo")
        if isinstance(commune_geo, dict) and commune_geo.get("champImport") == target_code:
            return {
                "communeAssociee": commune_geo.get("communeAssociee", ""),
                "communeMere": commune_geo.get("communeMere", ""),
            }
        # Chercher dans entreprise.commune
        entreprise = etab.get("entreprise")
        if isinstance(entreprise, dict):
            commune_ent = entreprise.get("commune")
            if isinstance(commune_ent, dict) and commune_ent.get("champImport") == target_code:
                return {
                    "communeAssociee": commune_ent.get("communeAssociee", ""),
                    "communeMere": commune_ent.get("communeMere", ""),
                }
    return None


def main():
    parser = argparse.ArgumentParser(description="Extraction des communes depuis i-taiete")
    parser.add_argument("--csv", default="exportrte.csv", help="Chemin vers exportrte.csv")
    parser.add_argument("--output", default="reference_data/communes.json", help="Fichier de sortie")
    args = parser.parse_args()

    print(f"Lecture du CSV {args.csv}...")
    commune_to_tahiti = extract_commune_tahiti_mapping(args.csv)
    print(f"{len(commune_to_tahiti)} codes communes uniques trouvés.")

    communes = {}
    errors = []
    total = len(commune_to_tahiti)

    for i, (code, tahiti) in enumerate(sorted(commune_to_tahiti.items())):
        code_int = int(code) if code.isdigit() else 0
        print(f"  [{i+1}/{total}] Code {code} (TAHITI {tahiti})...", end=" ", flush=True)

        data = call_old_server(tahiti)

        if isinstance(data, dict) and "_error" in data:
            print(f"ERREUR: {data['_error']}")
            errors.append((code, tahiti, data["_error"]))
            continue

        result = extract_commune_from_response(data, code_int)
        if result:
            communes[code] = result
            print(f"OK: {result['communeAssociee']} / {result['communeMere']}")
        else:
            print(f"NON TROUVE dans la reponse")
            errors.append((code, tahiti, "commune non trouvee dans la reponse"))

        # Petite pause pour ne pas surcharger l'API
        time.sleep(0.2)

    # Sauvegarder
    # Trier par code pour un JSON lisible
    sorted_communes = dict(sorted(communes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(sorted_communes, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Resultat: {len(communes)} communes extraites, {len(errors)} erreurs")
    print(f"Sauvegarde dans {args.output}")

    if errors:
        print(f"\nErreurs:")
        for code, tahiti, err in errors:
            print(f"  Code {code} (TAHITI {tahiti}): {err}")


if __name__ == "__main__":
    main()
