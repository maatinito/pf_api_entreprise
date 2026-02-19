#!/usr/bin/env python3
"""
Télécharge et met en cache les réponses i-taiete pour les numéros TAHITI du CSV.
Permet d'accélérer les comparaisons répétées (l'API est lente ~700ms/requête).

Usage:
  # Cache complet (toutes les entreprises — long !)
  python3 benchmark/cache_itaiete.py --csv exportrte.csv

  # Cache partiel des N derniers jours seulement
  python3 benchmark/cache_itaiete.py --csv exportrte.csv --recent-days 30

  # Cache N entreprises aléatoires
  python3 benchmark/cache_itaiete.py --csv exportrte.csv --count 500

  # Reprendre un cache interrompu (skip les déjà téléchargés)
  python3 benchmark/cache_itaiete.py --csv exportrte.csv --resume

Fichier de sortie: benchmark/cache_itaiete.json
"""

import argparse
import base64
import csv
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

OLD_BASE_URL = "https://api.gov.pf/i-taiete"
OLD_USER = "MES-DEMARCHES"
OLD_PASSWORD = "84b5b7f1-ec3c-4aa4-8bd9-74c9802233a9"
OLD_API_KEY = "5df5bc28-b64c-4dee-a34c-cd0dc63172bc"

DEFAULT_OUTPUT = "benchmark/cache_itaiete.json"


def call_old_server(numero_tahiti):
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


def parse_date(s):
    """Parse DD/MM/YYYY -> datetime. Retourne None si invalide."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def extract_tahiti_numbers(csv_path, recent_days=None, count=None, shuffle=True):
    """Extrait les numéros TAHITI uniques du CSV, avec filtrage optionnel."""
    cutoff = datetime.now() - timedelta(days=recent_days) if recent_days else None
    numbers = {}  # numtah -> date_inscription

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 34:
                continue
            numtah = row[0].strip()
            if not numtah or numtah in numbers:
                continue
            if cutoff:
                # Col 26: Insc_ENT (date inscription entreprise)
                date = parse_date(row[26])
                if not date or date < cutoff:
                    continue
            numbers[numtah] = row[26].strip()  # garder la date pour info

    result = list(numbers.keys())
    if shuffle:
        random.shuffle(result)
    if count:
        result = result[:count]
    return result


def load_cache(output_path):
    """Charge le cache existant."""
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache, output_path):
    """Sauvegarde le cache sur disque."""
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))


def main():
    parser = argparse.ArgumentParser(description="Cache i-taiete")
    parser.add_argument("--csv", default="exportrte.csv")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--recent-days", type=int, help="Limiter aux entreprises créées dans les N derniers jours")
    parser.add_argument("--count", type=int, help="Limiter à N entreprises aléatoires")
    parser.add_argument("--resume", action="store_true", help="Reprendre un cache interrompu")
    args = parser.parse_args()

    print(f"Extraction des numéros TAHITI depuis {args.csv}...")
    tahiti_numbers = extract_tahiti_numbers(args.csv, args.recent_days, args.count)
    print(f"{len(tahiti_numbers)} numéros TAHITI à télécharger.")

    cache = {}
    if args.resume:
        cache = load_cache(args.output)
        already = len(cache)
        tahiti_numbers = [n for n in tahiti_numbers if n not in cache]
        print(f"Reprise: {already} déjà en cache, {len(tahiti_numbers)} restants.")

    if not tahiti_numbers:
        print("Rien à télécharger.")
        return

    total = len(tahiti_numbers)
    errors = 0
    save_every = 50  # sauvegarder toutes les 50 requêtes

    print(f"Début du téléchargement... (sauvegarde tous les {save_every})")
    start = time.time()

    for i, num in enumerate(tahiti_numbers):
        result = call_old_server(num)
        if isinstance(result, dict) and "_error" in result:
            errors += 1
        cache[num] = result

        elapsed = time.time() - start
        rate = (i + 1) / elapsed
        remaining = (total - i - 1) / rate if rate > 0 else 0

        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{total}] {rate:.1f} req/s — reste ~{remaining/60:.1f}min — erreurs: {errors}")

        if (i + 1) % save_every == 0:
            save_cache(cache, args.output)

    save_cache(cache, args.output)

    elapsed = time.time() - start
    print(f"\nTerminé: {total} téléchargés en {elapsed:.1f}s ({total/elapsed:.1f} req/s)")
    print(f"Erreurs: {errors}")
    print(f"Cache sauvegardé dans {args.output}")


if __name__ == "__main__":
    main()
