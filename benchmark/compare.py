#!/usr/bin/env python3
"""
Benchmark & comparaison entre l'ancien serveur i-taiete et le nouveau pf-entreprise.

Test 1 : vitesse (chrono N requêtes sur chaque serveur)
Test 2 : comparaison structurelle champ par champ avec normalisation

Usage:
  1. Lancer le nouveau serveur en local :
     CSV_PATH=./exportrte.csv PORT=3000 ./pf-entreprise

  2. Lancer le script :
     python3 benchmark/compare.py

  Options :
     --count N        nombre de TAHITI à tester (défaut: 200)
     --csv PATH       chemin vers exportrte.csv pour extraire les numéros TAHITI
     --new-url URL    URL du nouveau serveur (défaut: http://localhost:3000)
     --speed-only     ne faire que le test de vitesse
     --compare-only   ne faire que le test de comparaison
"""

import argparse
import csv
import json
import random
import re
import sys
import time
import urllib.request
import urllib.error
import base64
from collections import defaultdict

# --- Config ancien serveur ---
OLD_BASE_URL = "https://api.gov.pf/i-taiete"
OLD_USER = "MES-DEMARCHES"
OLD_PASSWORD = "84b5b7f1-ec3c-4aa4-8bd9-74c9802233a9"
OLD_API_KEY = "5df5bc28-b64c-4dee-a34c-cd0dc63172bc"

# --- Config nouveau serveur ---
NEW_BASE_URL = "http://localhost:3000"


def extract_tahiti_numbers(csv_path, count):
    """Extrait des numéros TAHITI uniques depuis le CSV."""
    numbers = set()
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        if not header:
            print("ERREUR: CSV vide")
            sys.exit(1)
        for row in reader:
            if len(row) > 0 and row[0].strip():
                numbers.add(row[0].strip())
    numbers = list(numbers)
    random.shuffle(numbers)
    return numbers[:count]


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


def call_new_server(numero_tahiti, base_url):
    """Appelle le nouveau serveur pf-entreprise."""
    url = f"{base_url}/etablissements/Entreprise?numeroTahiti={numero_tahiti}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}"}
    except Exception as e:
        return {"_error": str(e)}


# ========== TEST 1 : VITESSE ==========

def speed_test(tahiti_numbers, new_base_url):
    """Compare la vitesse des deux serveurs."""
    count = len(tahiti_numbers)
    print(f"\n{'='*60}")
    print(f" TEST DE VITESSE — {count} requêtes")
    print(f"{'='*60}")

    # Nouveau serveur
    print(f"\n>> Nouveau serveur ({new_base_url})...")
    start = time.time()
    new_errors = 0
    for i, num in enumerate(tahiti_numbers):
        result = call_new_server(num, new_base_url)
        if isinstance(result, dict) and "_error" in result:
            new_errors += 1
        if (i + 1) % 50 == 0:
            print(f"   {i+1}/{count}...")
    new_time = time.time() - start

    # Ancien serveur
    print(f"\n>> Ancien serveur ({OLD_BASE_URL})...")
    start = time.time()
    old_errors = 0
    for i, num in enumerate(tahiti_numbers):
        result = call_old_server(num)
        if isinstance(result, dict) and "_error" in result:
            old_errors += 1
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            print(f"   {i+1}/{count}... ({elapsed:.1f}s)")
    old_time = time.time() - start

    # Résultats
    print(f"\n{'─'*60}")
    print(f" RÉSULTATS VITESSE")
    print(f"{'─'*60}")
    print(f" {'Serveur':<25} {'Temps total':>12} {'Moy/requête':>12} {'Erreurs':>8}")
    print(f" {'─'*25} {'─'*12} {'─'*12} {'─'*8}")
    print(f" {'Ancien (i-taiete)':<25} {old_time:>11.2f}s {old_time/count*1000:>10.1f}ms {old_errors:>8}")
    print(f" {'Nouveau (pf-entreprise)':<25} {new_time:>11.2f}s {new_time/count*1000:>10.1f}ms {new_errors:>8}")
    if new_time > 0:
        print(f"\n Accélération : x{old_time/new_time:.1f}")
    print()


# ========== TEST 2 : COMPARAISON ==========

def normalize(value):
    """Normalise une valeur pour comparaison souple."""
    if value is None:
        return None
    if isinstance(value, str):
        # Trim, lowercase, tirets/espaces unifiés
        v = value.strip().lower()
        v = re.sub(r"[\s\-_]+", " ", v)
        # Supprimer accents courants pour comparaison
        return v
    return value


def flatten_json(obj, prefix=""):
    """Aplatit un objet JSON en dict {chemin.champ: valeur}."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                items.update(flatten_json(v, path))
            else:
                items[path] = v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                items.update(flatten_json(v, path))
            else:
                items[path] = v
    return items


def generalize_key(key):
    """Remplace les indices de tableau par [*] pour regrouper les stats."""
    return re.sub(r"\[\d+\]", "[*]", key)


def compare_test(tahiti_numbers, new_base_url):
    """Compare les résultats des deux serveurs champ par champ."""
    count = len(tahiti_numbers)
    print(f"\n{'='*60}")
    print(f" TEST DE COMPARAISON — {count} entreprises")
    print(f"{'='*60}")

    # Stats par champ généralisé
    stats = defaultdict(lambda: {
        "total": 0,
        "identical": 0,
        "different": 0,
        "old_only": 0,
        "new_only": 0,
        "diff_examples": [],
    })

    errors_old = 0
    errors_new = 0
    both_empty = 0
    compared = 0

    for i, num in enumerate(tahiti_numbers):
        old_data = call_old_server(num)
        new_data = call_new_server(num, new_base_url)

        if (i + 1) % 50 == 0:
            print(f"   {i+1}/{count}...")

        # Ignorer les erreurs
        if isinstance(old_data, dict) and "_error" in old_data:
            errors_old += 1
            continue
        if isinstance(new_data, dict) and "_error" in new_data:
            errors_new += 1
            continue

        # Les deux retournent des listes d'établissements
        if not isinstance(old_data, list):
            old_data = [old_data] if old_data else []
        if not isinstance(new_data, list):
            new_data = [new_data] if new_data else []

        if len(old_data) == 0 and len(new_data) == 0:
            both_empty += 1
            continue

        compared += 1

        # Trier par numEtablissement pour éviter les faux positifs
        old_data.sort(key=lambda x: x.get("numEtablissement", 0))
        new_data.sort(key=lambda x: x.get("numEtablissement", 0))

        # Comparer les établissements un par un (par index)
        max_len = max(len(old_data), len(new_data))
        for idx in range(max_len):
            old_etab = old_data[idx] if idx < len(old_data) else {}
            new_etab = new_data[idx] if idx < len(new_data) else {}

            old_flat = flatten_json(old_etab)
            new_flat = flatten_json(new_etab)

            all_keys = set(old_flat.keys()) | set(new_flat.keys())

            for key in all_keys:
                gkey = generalize_key(key)
                s = stats[gkey]
                s["total"] += 1

                old_val = old_flat.get(key)
                new_val = new_flat.get(key)

                if key not in old_flat:
                    s["new_only"] += 1
                elif key not in new_flat:
                    s["old_only"] += 1
                elif normalize(old_val) == normalize(new_val):
                    s["identical"] += 1
                else:
                    s["different"] += 1
                    if len(s["diff_examples"]) < 3:
                        s["diff_examples"].append({
                            "tahiti": num,
                            "old": old_val,
                            "new": new_val,
                        })

    # Affichage des résultats
    print(f"\n{'─'*100}")
    print(f" RÉSULTATS COMPARAISON")
    print(f"{'─'*100}")
    print(f" Entreprises testées : {count}")
    print(f" Comparées (non vides): {compared}")
    print(f" Vides des 2 côtés   : {both_empty}")
    print(f" Erreurs ancien      : {errors_old}")
    print(f" Erreurs nouveau     : {errors_new}")
    print()

    # Tableau des stats
    header = f" {'Champ':<45} {'Total':>6} {'Ident.':>7} {'Diff.':>6} {'Ancien':>7} {'Nouveau':>8}"
    print(header)
    print(f" {'─'*45} {'─'*6} {'─'*7} {'─'*6} {'─'*7} {'─'*8}")

    for gkey in sorted(stats.keys()):
        s = stats[gkey]
        diff_marker = " ***" if s["different"] > 0 or s["old_only"] > 0 or s["new_only"] > 0 else ""
        print(f" {gkey:<45} {s['total']:>6} {s['identical']:>7} {s['different']:>6} {s['old_only']:>7} {s['new_only']:>8}{diff_marker}")

    # Exemples de différences
    has_diffs = {k: v for k, v in stats.items() if v["different"] > 0}
    if has_diffs:
        print(f"\n{'─'*100}")
        print(f" EXEMPLES DE DIFFÉRENCES (max 3 par champ)")
        print(f"{'─'*100}")
        for gkey in sorted(has_diffs.keys()):
            s = has_diffs[gkey]
            print(f"\n {gkey} ({s['different']} différences):")
            for ex in s["diff_examples"]:
                print(f"   TAHITI {ex['tahiti']}: ancien={ex['old']!r}  nouveau={ex['new']!r}")

    print()


# ========== MAIN ==========

def main():
    parser = argparse.ArgumentParser(description="Benchmark ancien vs nouveau serveur")
    parser.add_argument("--count", type=int, default=200, help="Nombre de TAHITI à tester (défaut: 200)")
    parser.add_argument("--csv", default="exportrte.csv", help="Chemin vers exportrte.csv")
    parser.add_argument("--new-url", default=NEW_BASE_URL, help="URL du nouveau serveur")
    parser.add_argument("--speed-only", action="store_true", help="Test de vitesse uniquement")
    parser.add_argument("--compare-only", action="store_true", help="Test de comparaison uniquement")
    args = parser.parse_args()

    print(f"Extraction de {args.count} numéros TAHITI depuis {args.csv}...")
    tahiti_numbers = extract_tahiti_numbers(args.csv, args.count)
    print(f"{len(tahiti_numbers)} numéros extraits.")

    if not args.compare_only:
        speed_test(tahiti_numbers, args.new_url)

    if not args.speed_only:
        compare_test(tahiti_numbers, args.new_url)


if __name__ == "__main__":
    main()
