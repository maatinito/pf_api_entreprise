# pf_api_entreprise

[![CI](https://github.com/maatinito/pf_api_entreprise/actions/workflows/ci.yml/badge.svg)](https://github.com/maatinito/pf_api_entreprise/actions/workflows/ci.yml)

Microservice Go servant les donnees des entreprises et etablissements de Polynesie francaise a partir du fichier CSV public de l'ISPF (`exportrte.csv`). Il remplace l'API externe `i-taiete` (`api.gov.pf`), sujette a des timeouts frequents, tout en conservant une compatibilite JSON stricte avec le `PfEtablissementAdapter` de [mes-demarches](https://github.com/maatinito/mes-demarches).

## Caracteristiques

- **Compatibilite i-taiete** -- le JSON retourne est identique a l'API originale, aucune modification cote Rails
- **Performant** -- index en memoire, reponse < 10 ms, ~115 000 etablissements charges au demarrage
- **Leger** -- image Docker de 27 Mo, consommation RAM < 100 Mo
- **Zero dependance externe** -- pas de base de donnees, stdlib Go + `golang.org/x/text` uniquement
- **Rechargement a chaud** -- endpoint `/admin/reload` pour mettre a jour le CSV sans redemarrage

## Demarrage rapide

### Avec Docker

```bash
docker build -t pf-entreprise .

docker run -p 3000:3000 -v /chemin/vers/exportrte.csv:/data/exportrte.csv pf-entreprise
```

### Sans Docker

```bash
# Pre-requis : Go 1.24+
go mod download

go build -o pf-entreprise .

CSV_PATH=./exportrte.csv PORT=3000 ./pf-entreprise
```

## API

### `GET /etablissements/Entreprise?numeroTahiti={XXXXXX}`

Retourne un tableau JSON de tous les etablissements lies au numero TAHITI (6 caracteres).

```bash
curl http://localhost:3000/etablissements/Entreprise?numeroTahiti=075390
```

<details>
<summary>Exemple de reponse</summary>

```json
[
  {
    "numeroTahitiEtablissement": "075390-001",
    "numEtablissement": 1,
    "nomCommercial": "SIEGE SOCIAL",
    "entreprise": {
      "numeroTahiti": "075390",
      "raisonSociale": "BANQUE SOCREDO",
      "sigle": "SOCREDO",
      "formeJuridique": { "code": "560", "libelle": "Societe Anonyme a Directoire (dont S.A.E.M.)" },
      "activitePrincipale": { "code": "6419Z", "libelle": "Autres intermediations monetaires" },
      "classeEffectif": { "id": 8, "libelle": "200 a 499 personnes" }
    },
    "activitePrincipale": { "code": "6419Z", "libelle": "Autres intermediations monetaires" },
    "communeGeo": {
      "champImport": 35000,
      "communeAssociee": "Papeete",
      "communeMere": "Papeete",
      "subdivision": { "champImport": 4, "libelle": "Iles Du Vent" }
    }
  }
]
```

</details>

### `GET /healthz`

Controle de sante. Retourne `200` quand le CSV est charge, `503` sinon.

```json
{ "status": "ok", "entries": 115603 }
```

### `POST /admin/reload`

Recharge le CSV a chaud. L'ancien index reste disponible pendant le chargement du nouveau (mutex RW).

```bash
curl -X POST http://localhost:3000/admin/reload
```

## Configuration

| Variable    | Defaut                 | Description                      |
|-------------|------------------------|----------------------------------|
| `PORT`      | `3000`                 | Port d'ecoute HTTP               |
| `CSV_PATH`  | `/data/exportrte.csv`  | Chemin vers le fichier CSV       |
| `LOG_LEVEL` | `info`                 | Niveau de log (debug, info, warn)|

## Source de donnees

Le fichier `exportrte.csv` est publie quotidiennement par l'ISPF sur [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/registre-du-commerce-et-des-societes-rcs-de-polynesie-francaise/).

- **Format** : CSV, separateur `;`, 34 colonnes
- **Encodage** : Windows-1252 ou UTF-8 (detection automatique)
- **Volume** : ~115 000 lignes

En production (Kubernetes), un CronJob telecharge le fichier dans un PVC et declenche un rechargement via `/admin/reload`.

## Tests

```bash
go test ./...

# Avec couverture
go test -cover ./...

# Verbose
go test -v ./...
```

## Architecture

```
main.go          -- Serveur HTTP, routing, demarrage
csv.go           -- Parsing CSV, detection d'encodage, construction de l'index
models.go        -- Structs Go correspondant au JSON i-taiete
reference.go     -- Tables de reference (NAF, formes juridiques, effectifs, communes)
handlers.go      -- Handlers HTTP (etablissements, healthz, reload)
reference_data/  -- Fichiers JSON embarques pour les tables de reference
main_test.go     -- Tests
Dockerfile       -- Build multi-stage (golang:1.24-alpine -> alpine:3.19)
```

## Benchmark et comparaison avec i-taiete

```bash
# Comparer les reponses avec i-taiete (50 entreprises)
python3 benchmark/compare.py --csv exportrte.csv --compare-only --count 50

# Mettre en cache les reponses i-taiete (evite les appels reseau repetes)
python3 benchmark/cache_itaiete.py --csv exportrte.csv --count 500 --output benchmark/cache.json

# Rapport entreprises creees dans le dernier mois
python3 benchmark/report_recent.py --csv exportrte.csv --cache benchmark/cache.json --days 30

# Mettre a jour la table des communes depuis i-taiete
python3 benchmark/extract_communes.py --csv exportrte.csv
```

## Licence

Projet interne [DINUM / Gouvernement de la Polynesie francaise](https://www.service-public.pf/).
