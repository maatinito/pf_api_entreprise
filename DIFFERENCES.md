# Différences pf-entreprise vs i-taiete

Ce fichier documente les différences constatées entre le nouveau serveur `pf-entreprise` et l'ancien serveur `i-taiete`, au fil des itérations de comparaison.

---

## Comment lancer une comparaison

```bash
# Comparaison complète sur tout le cache (< 3 min avec --new-workers 20)
python3 benchmark/compare.py --csv exportrte.csv --cache benchmark/cache_itaiete.json --compare-only --count 200000 --new-workers 20

# Vérifier les tests Go
go test ./...
```

---

## Itération 2 — 2026-03-09 (état courant)

### Corrigé dans cette itération

| Champ | Avant | Après | Fix |
|-------|-------|-------|-----|
| `adressePostale` (établissement) | **100% diff** | **100% identique** ✅ | Mis à `null` — i-taiete retourne null au niveau étab, on copiait depuis entreprise |
| `boitePostale` (établissement) | **65% diff** | **3% diff** ✅ | Mis à `null` — même raison |
| `activitePrincipale.libelle` (NAF) | labels approximatifs | labels exacts ✅ | 55 labels NAF mis à jour depuis le cache i-taiete |
| `entreprise.classeEffectif.libelle` (labels) | 3 labels faux | labels exacts ✅ | "3 à 5" → "3 à 4", "6 à 9" → "5 à 9", "500 à 999" → "500 et plus" |

### Faux positifs (différences sans impact réel)

Normalisés identiques par `normalize()` dans `compare.py` :
- `rue`, `immeuble`, `quartier`, `nomCommercial`, `adresseGeo`, `sigle` : `""` vs `null` — sémantiquement équivalent

### Différences de données irrémédiables

Ces différences existent parce que les deux systèmes ont des bases de données indépendantes qui ont divergé. Elles ne peuvent pas être corrigées depuis le CSV `exportrte.csv`.

| Champ | % diff | Raison |
|-------|--------|--------|
| `telephone` (étab.) | **78%** | i-taiete stockait les téléphones en base ; absent du CSV |
| `entreprise.commune.subdivision.libelle` | **33%** | 34% des entreprises ont `Com_BP_ENT=99999` (non déclaré) dans le CSV, mais i-taiete a leur vraie commune en base |
| `entreprise.classeEffectif.libelle` | **26%** | Codes effectif différents entre les deux bases (pas juste les labels) |
| `entreprise.adressePostale` | **14%** | Adresse postale différente entre les deux bases |
| `entreprise.boitePostale` | **12%** | Même raison |
| `entreprise.commune.*` | **5-6%** | Commune différente (liée à Com_BP_ENT=99999) |
| `dateModification` | **2%** | Timestamps de mise à jour indépendants |
| `adresseGeo` | **2%** | ADRGEO vide dans le CSV mais non-null dans i-taiete |
| `boitePostale` (étab.) | **3%** | i-taiete a des BP au niveau établissement pour ~5700 cas (champ absent du CSV) |
| `activiteSecondaires[*].code` | **1%** | Activités secondaires différentes entre les deux bases |
| `pointKilometrique` | **1%** | Format "20,6" vs "20.6" + données différentes |
| `communeGeo.*` | **~1%** | Commune géo différente pour ~1000 établissements |

### Champs ignorés dans la comparaison (champs techniques i-taiete)

Filtrés par `IGNORED_FIELDS` dans `compare.py` :
- `id`, `version`, `entreprise.id`, `entreprise.version` — auto-incréments et timestamps internes
- `activitePrincipale.id`, `activiteSecondaires[*].id` — auto-incréments
- `communeGeo.id`, `entreprise.commune.id`, `entreprise.formeJuridique.id`, `entreprise.classeEffectif.id` — auto-incréments

### Particularités de nettoyage de données

- **`nomCommercial` guillemets** (0.1%) : le CSV stocke des valeurs avec guillemets doublés CSV (`""X""`) qu'i-taiete a conservés littéralement dans sa base. Notre parser CSV les déséchapppe correctement. La différence est dans la donnée source d'i-taiete, pas dans notre traitement.
- **`entreprise.dateInscription` 1%** : ~1540 entreprises récentes inscrites après la prise du cache i-taiete (janvier–mars 2026). Notre CSV est plus récent.

---

## Itération 1 — 2026-03-09 (état de départ)

### Différences initiales significatives

| Champ | % diff |
|-------|--------|
| `adressePostale` (étab.) | 100% |
| `telephone` (étab.) | 78% |
| `boitePostale` (étab.) | 65% |
| `entreprise.commune.subdivision.libelle` | 33% |
| `entreprise.classeEffectif.libelle` | 26% |
| `entreprise.adressePostale` | 14% |
| `entreprise.boitePostale` | 12% |
| `activitePrincipale.libelle` (labels NAF) | ~1% (labels approximatifs) |

---

## Guide de workflow itératif

```
1. Lancer la comparaison :
   python3 benchmark/compare.py --csv exportrte.csv --cache benchmark/cache_itaiete.json \
     --compare-only --count 200000 --new-workers 20

2. Identifier les champs avec des différences > 1%

3. Distinguer : data difference (irrémédiable) vs bug de code (corrigeable)

4. Corriger dans le code ou les données de référence

5. go test ./... && go build -o pf-entreprise .

6. Recommencer depuis l'étape 1
```
