#!/usr/bin/env python3
"""
Benchmark & comparaison entre l'ancien serveur i-taiete et le nouveau pf-entreprise.

Test 1 : vitesse (chrono N requêtes sur chaque serveur)
Test 2 : comparaison structurelle champ par champ avec normalisation

Usage:
  # Tests complets (appels live)
  python3 benchmark/compare.py --csv exportrte.csv

  # Avec cache local (beaucoup plus rapide)
  python3 benchmark/compare.py --csv exportrte.csv --cache benchmark/cache_itaiete.json

  # Comparaison uniquement
  python3 benchmark/compare.py --csv exportrte.csv --cache benchmark/cache_itaiete.json --compare-only

Options:
  --count N        nombre de TAHITI à tester (défaut: 200)
  --csv PATH       chemin vers exportrte.csv
  --cache PATH     fichier cache i-taiete (créé par cache_itaiete.py)
  --new-url URL    URL du nouveau serveur (défaut: http://localhost:3000)
  --speed-only     test de vitesse uniquement
  --compare-only   test de comparaison uniquement
"""

import argparse
import csv
import json
import os
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


def load_cache(cache_path):
    """Charge le cache i-taiete depuis un fichier JSON."""
    if not cache_path or not os.path.exists(cache_path):
        return None
    print(f"Chargement du cache {cache_path}...")
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Cache chargé: {len(data)} entrées.")
    return data


def sort_activites_secondaires(etab):
    """Trie activiteSecondaires par code pour éviter les faux positifs d'ordre."""
    if not isinstance(etab, dict):
        return etab
    if "activiteSecondaires" in etab and isinstance(etab["activiteSecondaires"], list):
        etab["activiteSecondaires"].sort(
            key=lambda x: x.get("code", "") if isinstance(x, dict) else ""
        )
    return etab


def normalize_etablissements(data):
    """Normalise une liste d'établissements : tri + sort activités."""
    if not isinstance(data, list):
        data = [data] if data else []
    data.sort(key=lambda x: x.get("numEtablissement", 0) if isinstance(x, dict) else 0)
    return [sort_activites_secondaires(e) for e in data]


# ========== TEST 1 : VITESSE ==========

def speed_test(tahiti_numbers, new_base_url, cache=None):
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

    # Ancien serveur (ou cache)
    if cache is not None:
        print(f"\n>> Ancien serveur (depuis cache local)...")
        start = time.time()
        old_errors = sum(1 for n in tahiti_numbers if isinstance(cache.get(n), dict) and "_error" in cache.get(n, {}))
        old_time = time.time() - start
        print(f"   {count}/{count} (instantané depuis cache)")
    else:
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
    if cache is None:
        print(f" {'Ancien (i-taiete)':<25} {old_time:>11.2f}s {old_time/count*1000:>10.1f}ms {old_errors:>8}")
    print(f" {'Nouveau (pf-entreprise)':<25} {new_time:>11.2f}s {new_time/count*1000:>10.1f}ms {new_errors:>8}")
    if cache is None and new_time > 0:
        print(f"\n Accélération : x{old_time/new_time:.1f}")
    print()


# ========== TEST 2 : COMPARAISON ==========

def normalize(value):
    """Normalise une valeur pour comparaison souple."""
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        v = re.sub(r"[\s\-_]+", " ", v)
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


# Champs à ignorer dans la comparaison (différences structurelles connues)
IGNORED_FIELDS = {
    "id",                            # auto-increment
    "version",                       # timestamp interne i-taiete
    "entreprise.id",                 # auto-increment
    "entreprise.version",            # timestamp interne
    "entreprise.telephone",          # absent du CSV
    "entreprise.email",              # absent du CSV
    "activitePrincipale.id",         # auto-increment
    "activiteSecondaires[*].id",     # auto-increment
    "communeGeo.id",                 # auto-increment
    "entreprise.activitePrincipale.id",  # auto-increment
    "entreprise.commune.id",         # auto-increment
    "entreprise.formeJuridique.id",  # auto-increment
    "entreprise.classeEffectif.id",  # auto-increment
    "communeGeo.subdivision.id",     # auto-increment
    "entreprise.commune.subdivision.id",  # auto-increment
}


def compare_test(tahiti_numbers, new_base_url, cache=None, show_ignored=False):
    """Compare les résultats des deux serveurs champ par champ."""
    count = len(tahiti_numbers)
    source = "cache local" if cache is not None else OLD_BASE_URL
    print(f"\n{'='*60}")
    print(f" TEST DE COMPARAISON — {count} entreprises (source: {source})")
    print(f"{'='*60}")

    stats = defaultdict(lambda: {
        "total": 0, "identical": 0, "different": 0,
        "old_only": 0, "new_only": 0, "diff_examples": [],
    })

    errors_old = 0
    errors_new = 0
    both_empty = 0
    old_missing = 0  # présent dans nouveau mais pas dans cache/ancien
    compared = 0

    for i, num in enumerate(tahiti_numbers):
        # Récupérer données ancien serveur
        if cache is not None:
            old_data = cache.get(num)
            if old_data is None:
                old_missing += 1
                old_data = []
        else:
            old_data = call_old_server(num)

        new_data = call_new_server(num, new_base_url)

        if (i + 1) % 100 == 0:
            print(f"   {i+1}/{count}...")

        if isinstance(old_data, dict) and "_error" in old_data:
            errors_old += 1
            continue
        if isinstance(new_data, dict) and "_error" in new_data:
            errors_new += 1
            continue

        old_data = normalize_etablissements(old_data)
        new_data = normalize_etablissements(new_data)

        if len(old_data) == 0 and len(new_data) == 0:
            both_empty += 1
            continue

        compared += 1
        max_len = max(len(old_data), len(new_data))

        for idx in range(max_len):
            old_etab = old_data[idx] if idx < len(old_data) else {}
            new_etab = new_data[idx] if idx < len(new_data) else {}

            old_flat = flatten_json(old_etab)
            new_flat = flatten_json(new_etab)
            all_keys = set(old_flat.keys()) | set(new_flat.keys())

            for key in all_keys:
                gkey = generalize_key(key)
                if not show_ignored and gkey in IGNORED_FIELDS:
                    continue
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
                        s["diff_examples"].append({"tahiti": num, "old": old_val, "new": new_val})

    # Affichage
    print(f"\n{'─'*100}")
    print(f" RÉSULTATS COMPARAISON")
    print(f"{'─'*100}")
    print(f" Entreprises testées  : {count}")
    print(f" Comparées            : {compared}")
    print(f" Vides des 2 côtés   : {both_empty}")
    print(f" Erreurs ancien       : {errors_old}")
    print(f" Erreurs nouveau      : {errors_new}")
    if cache is not None:
        print(f" Absentes du cache   : {old_missing}")
    print()

    # Séparer champs OK / avec différences
    ok_fields = {k: v for k, v in stats.items() if v["different"] == 0 and v["old_only"] == 0 and v["new_only"] == 0}
    diff_fields = {k: v for k, v in stats.items() if v["different"] > 0 or v["old_only"] > 0 or v["new_only"] > 0}

    print(f" Champs parfaitement identiques : {len(ok_fields)}")
    print(f" Champs avec différences        : {len(diff_fields)}")
    print()

    header = f" {'Champ':<50} {'Total':>6} {'Ident.':>7} {'Diff.':>6} {'Anc.':>5} {'Nouv.':>6}"
    print(header)
    print(f" {'─'*50} {'─'*6} {'─'*7} {'─'*6} {'─'*5} {'─'*6}")

    for gkey in sorted(diff_fields.keys()):
        s = diff_fields[gkey]
        total = s["total"]
        pct_ok = s["identical"] / total * 100 if total > 0 else 0
        print(f" {gkey:<50} {total:>6} {s['identical']:>6} ({pct_ok:4.0f}%) {s['different']:>6} {s['old_only']:>5} {s['new_only']:>6}")

    if ok_fields:
        print(f"\n Champs OK (100% identiques) : {', '.join(sorted(ok_fields.keys()))}")

    # Exemples de différences
    if diff_fields:
        print(f"\n{'─'*100}")
        print(f" EXEMPLES DE DIFFÉRENCES")
        print(f"{'─'*100}")
        for gkey in sorted(diff_fields.keys()):
            s = diff_fields[gkey]
            if s["different"] > 0:
                total = s["total"]
                pct = s["different"] / total * 100
                print(f"\n {gkey} ({s['different']}/{total} = {pct:.0f}% de différences):")
                for ex in s["diff_examples"]:
                    print(f"   TAHITI {ex['tahiti']}: ancien={ex['old']!r}  nouveau={ex['new']!r}")

    print()


# ========== MAIN ==========

def main():
    parser = argparse.ArgumentParser(description="Benchmark ancien vs nouveau serveur")
    parser.add_argument("--count", type=int, default=200, help="Nombre de TAHITI à tester (défaut: 200)")
    parser.add_argument("--csv", default="exportrte.csv", help="Chemin vers exportrte.csv")
    parser.add_argument("--cache", help="Fichier cache i-taiete (créé par cache_itaiete.py)")
    parser.add_argument("--new-url", default=NEW_BASE_URL, help="URL du nouveau serveur")
    parser.add_argument("--speed-only", action="store_true", help="Test de vitesse uniquement")
    parser.add_argument("--compare-only", action="store_true", help="Test de comparaison uniquement")
    parser.add_argument("--show-ignored", action="store_true", help="Afficher aussi les champs ignorés (IDs, version...)")
    args = parser.parse_args()

    cache = load_cache(args.cache)

    print(f"Extraction de {args.count} numéros TAHITI depuis {args.csv}...")
    tahiti_numbers = extract_tahiti_numbers(args.csv, args.count)

    # Si cache fourni, filtrer sur les numéros présents dans le cache
    if cache is not None:
        in_cache = [n for n in tahiti_numbers if n in cache]
        print(f"{len(in_cache)}/{len(tahiti_numbers)} numéros présents dans le cache.")
        tahiti_numbers = in_cache

    print(f"{len(tahiti_numbers)} numéros à comparer.")

    if not args.compare_only:
        speed_test(tahiti_numbers, args.new_url, cache)

    if not args.speed_only:
        compare_test(tahiti_numbers, args.new_url, cache, args.show_ignored)


if __name__ == "__main__":
    main()
