#!/usr/bin/env python3
"""
Rapport sur les entreprises créées/modifiées récemment.

Compare les entreprises du dernier mois entre le CSV (nouveau serveur)
et i-taiete (ancien serveur ou cache local).

Rapporte :
  - Combien sont présentes dans les deux
  - Combien sont absentes de i-taiete (nouvelles depuis le dernier export ?)
  - Différences de données pour celles qui sont dans les deux

Usage:
  # Avec le nouveau serveur en cours d'exécution + cache
  python3 benchmark/report_recent.py --csv exportrte.csv --cache benchmark/cache_itaiete.json

  # Sans cache (appels live à i-taiete, lent)
  python3 benchmark/report_recent.py --csv exportrte.csv

  # Sur les 60 derniers jours
  python3 benchmark/report_recent.py --csv exportrte.csv --days 60
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timedelta

OLD_BASE_URL = "https://api.gov.pf/i-taiete"
OLD_USER = "MES-DEMARCHES"
OLD_PASSWORD = "84b5b7f1-ec3c-4aa4-8bd9-74c9802233a9"
OLD_API_KEY = "5df5bc28-b64c-4dee-a34c-cd0dc63172bc"
NEW_BASE_URL = "http://localhost:3000"


def parse_date_csv(s):
    """Parse DD/MM/YYYY -> datetime."""
    if not s or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def extract_recent_tahiti(csv_path, days):
    """
    Extrait les numéros TAHITI dont la date d'inscription entreprise
    ou établissement est dans les N derniers jours.
    Retourne un dict {numtah: {date_inscription, date_modification}}.
    """
    cutoff = datetime.now() - timedelta(days=days)
    result = {}

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader, None)  # skip header
        for row in reader:
            if len(row) < 34:
                continue
            numtah = row[0].strip()
            if not numtah:
                continue
            # Col 26: Insc_ENT, Col 27: Mod_ENT, Col 30: Insc_ETA, Col 31: Mod_ETA
            dates_to_check = [row[26], row[27], row[30], row[31]]
            recent = any(
                d and (dt := parse_date_csv(d)) and dt >= cutoff
                for d in dates_to_check
                if (dt := parse_date_csv(d))
            )
            if recent and numtah not in result:
                result[numtah] = {
                    "insc_ent": row[26].strip(),
                    "mod_ent": row[27].strip(),
                    "raison_sociale": row[1].strip(),
                }

    return result


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


def call_new_server(numero_tahiti, base_url):
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
    if not cache_path or not os.path.exists(cache_path):
        return None
    print(f"Chargement du cache {cache_path}...")
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Cache chargé: {len(data)} entrées.")
    return data


def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        v = re.sub(r"[\s\-_]+", " ", v)
        return v
    return value


IGNORED_FIELDS = {
    "id", "version", "entreprise.id", "entreprise.version",
    "entreprise.telephone", "entreprise.email",
    "activitePrincipale.id", "activiteSecondaires[*].id",
    "communeGeo.id", "entreprise.activitePrincipale.id",
    "entreprise.commune.id", "entreprise.formeJuridique.id",
    "entreprise.classeEffectif.id", "communeGeo.subdivision.id",
    "entreprise.commune.subdivision.id",
}


def flatten_json(obj, prefix=""):
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
    return re.sub(r"\[\d+\]", "[*]", key)


def main():
    parser = argparse.ArgumentParser(description="Rapport entreprises récentes")
    parser.add_argument("--csv", default="exportrte.csv")
    parser.add_argument("--cache", help="Fichier cache i-taiete")
    parser.add_argument("--new-url", default=NEW_BASE_URL)
    parser.add_argument("--days", type=int, default=30, help="Fenêtre en jours (défaut: 30)")
    parser.add_argument("--count", type=int, default=0, help="Limite le nombre d'entreprises testées (0 = toutes)")
    args = parser.parse_args()

    cache = load_cache(args.cache)

    print(f"\nExtraction des entreprises des {args.days} derniers jours depuis {args.csv}...")
    recent = extract_recent_tahiti(args.csv, args.days)
    print(f"{len(recent)} entreprises/établissements récents trouvés.")

    if not recent:
        print("Aucune entreprise récente trouvée.")
        sys.exit(0)

    # Statuts
    in_both = []        # présent dans les deux
    only_in_new = []    # présent dans nouveau, absent de i-taiete
    only_in_old = []    # présent dans i-taiete, absent de notre CSV (ne devrait pas arriver)
    errors = []

    diff_stats = defaultdict(lambda: {"total": 0, "identical": 0, "different": 0, "diff_examples": []})

    import random
    tahiti_list = sorted(recent.keys())
    if args.count and args.count < len(tahiti_list):
        tahiti_list = random.sample(tahiti_list, args.count)
    total = len(tahiti_list)

    print(f"\nComparaison en cours...")
    for i, num in enumerate(tahiti_list):
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{total}...")

        # Données ancien serveur
        if cache is not None:
            old_data = cache.get(num)
            if old_data is None:
                old_data = []
        else:
            old_data = call_old_server(num)
            time.sleep(0.1)  # pas surcharger

        # Données nouveau serveur
        new_data = call_new_server(num, args.new_url)

        # Gérer les erreurs
        if isinstance(old_data, dict) and "_error" in old_data:
            errors.append((num, f"ancien: {old_data['_error']}"))
            continue
        if isinstance(new_data, dict) and "_error" in new_data:
            errors.append((num, f"nouveau: {new_data['_error']}"))
            continue

        if not isinstance(old_data, list):
            old_data = [old_data] if old_data else []
        if not isinstance(new_data, list):
            new_data = [new_data] if new_data else []

        old_empty = len(old_data) == 0
        new_empty = len(new_data) == 0

        if old_empty and not new_empty:
            only_in_new.append(num)
        elif not old_empty and new_empty:
            only_in_old.append(num)
        elif not old_empty and not new_empty:
            in_both.append(num)
            # Comparer champ par champ
            old_data.sort(key=lambda x: x.get("numEtablissement", 0) if isinstance(x, dict) else 0)
            new_data.sort(key=lambda x: x.get("numEtablissement", 0) if isinstance(x, dict) else 0)
            for etab in old_data + new_data:
                if isinstance(etab, dict) and isinstance(etab.get("activiteSecondaires"), list):
                    etab["activiteSecondaires"].sort(key=lambda x: x.get("code", "") if isinstance(x, dict) else "")
            max_len = max(len(old_data), len(new_data))
            for idx in range(max_len):
                old_etab = old_data[idx] if idx < len(old_data) else {}
                new_etab = new_data[idx] if idx < len(new_data) else {}
                old_flat = flatten_json(old_etab)
                new_flat = flatten_json(new_etab)
                all_keys = set(old_flat.keys()) | set(new_flat.keys())
                for key in all_keys:
                    gkey = generalize_key(key)
                    if gkey in IGNORED_FIELDS:
                        continue
                    s = diff_stats[gkey]
                    s["total"] += 1
                    old_val = old_flat.get(key)
                    new_val = new_flat.get(key)
                    if key not in old_flat or key not in new_flat:
                        s["different"] += 1
                    elif normalize(old_val) == normalize(new_val):
                        s["identical"] += 1
                    else:
                        s["different"] += 1
                        if len(s["diff_examples"]) < 3:
                            s["diff_examples"].append({"tahiti": num, "old": old_val, "new": new_val})

    # ========== RAPPORT ==========
    cutoff_str = (datetime.now() - timedelta(days=args.days)).strftime("%d/%m/%Y")
    print(f"\n{'='*70}")
    print(f" RAPPORT ENTREPRISES RÉCENTES (depuis {cutoff_str})")
    print(f"{'='*70}")
    print(f"\n Entreprises récentes dans le CSV : {total}")
    print(f" Présentes dans les deux          : {len(in_both)} ({len(in_both)/total*100:.0f}%)")
    print(f" Absentes de i-taiete             : {len(only_in_new)} ({len(only_in_new)/total*100:.0f}%)")
    print(f" Absentes du CSV (inattendu)       : {len(only_in_old)}")
    print(f" Erreurs                           : {len(errors)}")

    if only_in_new:
        print(f"\n{'─'*70}")
        print(f" ABSENTES DE I-TAIETE ({len(only_in_new)} entreprises)")
        print(f"{'─'*70}")
        for num in only_in_new[:20]:
            info = recent[num]
            print(f"  TAHITI {num}: {info['raison_sociale']} (inscrit le {info['insc_ent']})")
        if len(only_in_new) > 20:
            print(f"  ... et {len(only_in_new) - 20} autres")

    if in_both and diff_stats:
        print(f"\n{'─'*70}")
        print(f" DIFFÉRENCES SUR LES {len(in_both)} ENTREPRISES PRÉSENTES DANS LES DEUX")
        print(f"{'─'*70}")
        diff_fields = {k: v for k, v in diff_stats.items() if v["different"] > 0}
        ok_fields = {k: v for k, v in diff_stats.items() if v["different"] == 0}
        print(f" Champs OK : {len(ok_fields)}   Champs avec diffs : {len(diff_fields)}")
        print()

        header = f" {'Champ':<50} {'Total':>6} {'Ident.':>7} {'Diff.':>7}"
        print(header)
        print(f" {'─'*50} {'─'*6} {'─'*7} {'─'*7}")
        for gkey in sorted(diff_fields.keys()):
            s = diff_fields[gkey]
            pct = s["different"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f" {gkey:<50} {s['total']:>6} {s['identical']:>7} {s['different']:>6} ({pct:.0f}%)")

        has_examples = {k: v for k, v in diff_fields.items() if v["diff_examples"]}
        if has_examples:
            print(f"\n Exemples de différences:")
            for gkey in sorted(has_examples.keys()):
                s = has_examples[gkey]
                print(f"\n  {gkey}:")
                for ex in s["diff_examples"]:
                    print(f"    TAHITI {ex['tahiti']}: ancien={ex['old']!r}  nouveau={ex['new']!r}")

    if errors:
        print(f"\n{'─'*70}")
        print(f" ERREURS ({len(errors)})")
        for num, err in errors[:10]:
            print(f"  TAHITI {num}: {err}")

    print()


if __name__ == "__main__":
    main()
