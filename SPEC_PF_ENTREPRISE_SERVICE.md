# Spécification du service pf-entreprise (Go)

**Date:** 2026-02-07
**Objectif:** Ce document sert de brief complet pour implémenter le microservice Go dans un repo séparé.

---

## 1. Contexte

### 1.1 Problème
L'API externe `i-taiete` (hébergée sur `api.gov.pf`) est instable (timeouts fréquents). Elle sert les données des entreprises et établissements de Polynésie française à partir d'un fichier CSV public.

### 1.2 Solution
Un microservice Go léger déployé dans le cluster Kubernetes de mes-demarches, qui :
- Charge le CSV `exportrte.csv` en mémoire
- Sert un endpoint HTTP compatible avec l'API i-taiete actuelle
- Est mis à jour quotidiennement via un CronJob K8s externe

### 1.3 Contraintes
- **Compatibilité stricte** : le JSON retourné doit être identique à celui d'i-taiete (le code Rails `PfEtablissementAdapter` ne sera PAS modifié)
- **Performance** : temps de réponse < 10ms
- **Empreinte** : < 100 Mo RAM, image Docker < 30 Mo
- **Aucune dépendance externe** : pas de base de données, pas de Redis requis (cache optionnel futur)

---

## 2. Source de données

### 2.1 Fichier CSV
- **URL publique** : `https://www.data.gouv.fr/api/1/datasets/r/34184a7f-a4bf-4cf3-ac36-531388f3a6cb`
- **Nom** : `exportrte.csv`
- **Taille** : ~115 603 lignes, 34 colonnes
- **Séparateur** : point-virgule (`;`)
- **Encodage** : Windows-1252 ou UTF-8 (à détecter/gérer les deux cas)
- **Fréquence de mise à jour** : quotidienne
- **Chemin dans le conteneur** : `/data/exportrte.csv` (volume PVC monté par K8s)

### 2.2 Colonnes du CSV (34 colonnes, dans l'ordre)

```
Numtah;Nom_ENT;Sigle_ENT;code_Fjur;NAF2008_ENT;Classe_Effectifs;
Code_Postal_ENT;BP_ENT;Com_BP_ENT;NumETA;NumtahETA;Nom_ETAB;
Com_ETAB;Com_ETAB_libelle;PK;Quartier;Num_adr;Rue;Immeuble;ADRGEO;
NAF2008_ETAB;NAF2008_ETAB_1;NAF2008_ETAB_2;NAF2008_ETAB_3;NAF2008_ETAB_4;NAF2008_ETAB_5;
Insc_ENT;Mod_ENT;Rad_ENT;Reins_ENT;Insc_ETAB;Mod_ETAB;Rad_ETAB;Reins_ETAB
```

#### Colonnes ENTREPRISE (niveau société)
| # | Colonne          | Description                          | Exemple                 |
|---|------------------|--------------------------------------|-------------------------|
| 0 | Numtah           | Numéro TAHITI entreprise (6 chars)   | `000026`                |
| 1 | Nom_ENT          | Raison sociale                       | `HAUT-COMMISSARIAT...`  |
| 2 | Sigle_ENT        | Sigle                                | `HAUSSARIAT`            |
| 3 | code_Fjur        | Code forme juridique                 | `710`                   |
| 4 | NAF2008_ENT      | Code NAF niveau entreprise           | `8411Z`                 |
| 5 | Classe_Effectifs | Code classe d'effectifs (2 chars)    | `08`                    |
| 6 | Code_Postal_ENT  | Code postal + libellé                | `98713 PAPEETE BP`      |
| 7 | BP_ENT           | Numéro de boîte postale              | `115`                   |
| 8 | Com_BP_ENT       | Code commune BP (5 chars)            | `35000`                 |

#### Colonnes ETABLISSEMENT (niveau local)
| #  | Colonne          | Description                          | Exemple                 |
|----|------------------|--------------------------------------|-------------------------|
| 9  | NumETA           | Numéro d'établissement (3 chars)     | `001`                   |
| 10 | NumtahETA        | Numéro TAHITI établissement          | `000026-001`            |
| 11 | Nom_ETAB         | Nom commercial                       | `HAUT-COMMISSARIAT`     |
| 12 | Com_ETAB         | Code commune établissement (5 chars) | `35000`                 |
| 13 | Com_ETAB_libelle | Libellé de la commune                | `Papeete`               |
| 14 | PK               | Point kilométrique                   | (vide)                  |
| 15 | Quartier         | Nom du quartier                      | (vide)                  |
| 16 | Num_adr          | Numéro dans la rue                   | (vide)                  |
| 17 | Rue              | Nom de la rue                        | `Avenue Bruat`          |
| 18 | Immeuble         | Nom de l'immeuble                    | (vide)                  |
| 19 | ADRGEO           | Adresse géographique complémentaire  | `""`                    |
| 20 | NAF2008_ETAB     | Code NAF principal établissement     | `8411Z`                 |
| 21 | NAF2008_ETAB_1   | Code NAF secondaire 1                | `8411Z`                 |
| 22 | NAF2008_ETAB_2   | Code NAF secondaire 2                | (vide)                  |
| 23 | NAF2008_ETAB_3   | Code NAF secondaire 3                | (vide)                  |
| 24 | NAF2008_ETAB_4   | Code NAF secondaire 4                | (vide)                  |
| 25 | NAF2008_ETAB_5   | Code NAF secondaire 5                | (vide)                  |

#### Colonnes DATES
| #  | Colonne    | Description                        | Format       | Exemple        |
|----|------------|------------------------------------|--------------|----------------|
| 26 | Insc_ENT   | Date inscription entreprise        | DD/MM/YYYY   | `01/01/1991`   |
| 27 | Mod_ENT    | Date modification entreprise       | DD/MM/YYYY   | `01/09/2022`   |
| 28 | Rad_ENT    | Date radiation entreprise          | DD/MM/YYYY   | (vide)         |
| 29 | Reins_ENT  | Date réinscription entreprise      | DD/MM/YYYY   | (vide)         |
| 30 | Insc_ETAB  | Date inscription établissement     | DD/MM/YYYY   | `01/01/1991`   |
| 31 | Mod_ETAB   | Date modification établissement    | DD/MM/YYYY   | `11/08/2009`   |
| 32 | Rad_ETAB   | Date radiation établissement       | DD/MM/YYYY   | (vide)         |
| 33 | Reins_ETAB | Date réinscription établissement   | DD/MM/YYYY   | (vide)         |

---

## 3. Contrat d'API

### 3.1 Endpoint principal

```
GET /etablissements/Entreprise?numeroTahiti={XXXXXX}
```

- **Paramètre** : `numeroTahiti` - chaîne de 6 caractères (zéro-paddé)
- **Réponse** : tableau JSON d'établissements (peut contenir 0, 1 ou N résultats)
- **Content-Type** : `application/json; charset=utf-8`

### 3.2 Format de réponse JSON (contrat i-taiete exact)

```json
[
  {
    "id": 10642,
    "entreprise": {
      "id": 5159,
      "numeroTahiti": "075390",
      "raisonSociale": "BANQUE SOCREDO  ",
      "sigle": "SOCREDO",
      "classeEffectif": {
        "id": 8,
        "libelle": "200 à 499 personnes"
      },
      "formeJuridique": {
        "id": 23,
        "code": "560",
        "libelle": "Société Anonyme à Directoire (dont S.A.E.M.)"
      },
      "email": null,
      "adressePostale": "98713 PAPEETE BP",
      "boitePostale": "130",
      "version": null
    },
    "numEtablissement": 2,
    "nomCommercial": "AGENCE DE UTUROA",
    "boitePostale": null,
    "adressePostale": null,
    "telephone": null,
    "fax": null,
    "pointKilometrique": null,
    "quartier": null,
    "adresseGeo": "Centre villeRaiatea",
    "communeGeo": {
      "id": 352,
      "communeAssociee": "Uturoa",
      "communeMere": "Uturoa",
      "subdivision": {
        "id": 2,
        "libelle": "Iles Sous-Le-Vent"
      },
      "champImport": 58000
    },
    "rue": null,
    "immeuble": null,
    "activitePrincipale": {
      "id": 560,
      "code": "6419Z",
      "libelle": "Autres intermédiations monétaires"
    },
    "activiteSecondaires": [
      {
        "id": 560,
        "code": "6419Z",
        "libelle": "Autres intermédiations monétaires"
      }
    ],
    "dateInscription": "1987-08-13",
    "dateModification": "2003-07-24",
    "dateReinscription": null,
    "dateRadiation": null,
    "version": null,
    "contacts": []
  }
]
```

### 3.3 Champs JSON - règles de mapping

#### Niveau racine (établissement)

| Champ JSON          | Source CSV         | Transformation                                          |
|---------------------|--------------------|---------------------------------------------------------|
| id                  | (généré)           | Hash stable ou auto-increment basé sur l'index CSV      |
| numEtablissement    | NumETA             | Convertir en entier : `"001"` → `1`                     |
| nomCommercial       | Nom_ETAB           | Tel quel (conserver les espaces trailing)                |
| boitePostale        | (non disponible)   | `null`                                                  |
| adressePostale      | (non disponible)   | `null`                                                  |
| telephone           | (non disponible)   | `null`                                                  |
| fax                 | (non disponible)   | `null`                                                  |
| pointKilometrique   | PK                 | `null` si vide, sinon valeur brute                      |
| quartier            | Quartier           | `null` si vide, sinon valeur brute                      |
| adresseGeo          | ADRGEO             | `null` si vide ou `""`, sinon valeur brute              |
| rue                 | Rue                | `null` si vide, sinon valeur brute                      |
| immeuble            | Immeuble           | `null` si vide, sinon valeur brute                      |
| dateInscription     | Insc_ETAB          | Format `DD/MM/YYYY` → `YYYY-MM-DD`, `null` si vide     |
| dateModification    | Mod_ETAB           | Idem                                                    |
| dateRadiation       | Rad_ETAB           | Idem                                                    |
| dateReinscription   | Reins_ETAB         | Idem                                                    |
| version             | (non disponible)   | `null`                                                  |
| contacts            | (non disponible)   | `[]` (tableau vide)                                     |

#### Objet `entreprise`

| Champ JSON                  | Source CSV       | Transformation                              |
|-----------------------------|------------------|---------------------------------------------|
| entreprise.id               | (généré)         | Hash ou auto-increment par Numtah unique    |
| entreprise.numeroTahiti     | Numtah           | Tel quel                                    |
| entreprise.raisonSociale    | Nom_ENT          | Tel quel (conserver espaces trailing)        |
| entreprise.sigle            | Sigle_ENT        | Tel quel                                    |
| entreprise.email            | (non disponible) | `null`                                      |
| entreprise.adressePostale   | Code_Postal_ENT  | Tel quel                                    |
| entreprise.boitePostale     | BP_ENT           | `null` si vide, sinon valeur brute          |
| entreprise.version          | (non disponible) | `null`                                      |

#### Objet `entreprise.classeEffectif`

| Champ JSON | Source CSV       | Transformation                                    |
|------------|------------------|---------------------------------------------------|
| id         | Classe_Effectifs | Convertir en entier : `"08"` → `8`                |
| libelle    | (table référence)| Lookup dans la table des classes d'effectifs       |

**Table des classes d'effectifs :**
```
00 → "0 salarié"
01 → "1 à 2 salariés"
02 → "3 à 5 salariés"
03 → "6 à 9 salariés"
04 → "10 à 19 salariés"
05 → "20 à 49 salariés"
06 → "50 à 99 salariés"
07 → "100 à 199 personnes"
08 → "200 à 499 personnes"
09 → "500 à 999 personnes"
10 → "1000 à 1999 personnes"
11 → "2000 à 4999 personnes"
12 → "5000 à 9999 personnes"
13 → "10000 personnes et plus"
```

#### Objet `entreprise.formeJuridique`

| Champ JSON | Source CSV | Transformation                                         |
|------------|------------|--------------------------------------------------------|
| id         | (généré)   | Auto-increment par code unique                         |
| code       | code_Fjur  | Tel quel                                               |
| libelle    | (table réf)| Lookup dans la table des formes juridiques             |

**Table des formes juridiques** (extraire du CSV les valeurs distinctes de `code_Fjur`, puis associer les libellés). Exemples connus :
```
100 → "Entreprise individuelle"
200 → "Société en Nom Collectif (SNC)"
300 → "Société en Commandite Simple"
400 → "Société à Responsabilité Limitée (SARL)"
410 → "SARL Unipersonnelle (EURL)"
500 → "Société Anonyme (SA)"
510 → "SA à Conseil d'Administration"
560 → "Société Anonyme à Directoire (dont S.A.E.M.)"
600 → "Société par Actions Simplifiée (SAS)"
610 → "SAS Unipersonnelle (SASU)"
710 → "Organisme de droit public"
720 → "Etablissement public"
900 → "Autre forme juridique"
```

> **IMPORTANT** : cette table doit être complète. Lors de la première exécution, le service doit logguer un WARNING pour tout `code_Fjur` présent dans le CSV mais absent de la table de référence. Cela permettra de compléter la table progressivement.

#### Objet `communeGeo`

| Champ JSON       | Source CSV       | Transformation                              |
|------------------|------------------|---------------------------------------------|
| id               | (généré)         | Auto-increment par code commune unique      |
| communeAssociee  | Com_ETAB_libelle | Tel quel                                    |
| communeMere      | Com_ETAB_libelle | Identique à communeAssociee (simplification)|
| champImport      | Com_ETAB         | Convertir en entier : `"35000"` → `35000`  |

#### Objet `communeGeo.subdivision`

| Champ JSON | Source CSV | Transformation                                        |
|------------|------------|-------------------------------------------------------|
| id         | (généré)   | Auto-increment par subdivision unique                 |
| libelle    | (table réf)| Lookup basé sur le code commune                       |

**Table des subdivisions** (mapping code commune → subdivision) :
```
Code commune commence par :
- 10xxx, 11xxx, 12xxx, 13xxx, 14xxx, 15xxx, 16xxx → "Iles Du Vent"
  (Arue, Faaa, Mahina, Moorea, Paea, Papara, Papeete, Pirae, Punaauia, Taravao, etc.)
- 20xxx, 21xxx → "Iles Du Vent" (Communes associées IDV)
- 35xxx → "Iles Du Vent" (Papeete et communes proches)
- 40xxx, 50xxx, 55xxx, 58xxx → "Iles Sous-Le-Vent"
  (Bora-Bora, Huahine, Raiatea, Tahaa, etc.)
- 60xxx, 65xxx, 70xxx → "Iles Tuamotu-Gambier"
- 75xxx, 80xxx → "Iles Marquises"
- 85xxx, 90xxx → "Iles Australes"
- 99xxx → "Non déclaré"
```

> **IMPORTANT** : ce mapping est une approximation. Extraire les associations exactes code→subdivision depuis le CSV (DISTINCT sur Com_ETAB + lookup géographique connu). En cas de doute, logguer un WARNING et utiliser `"Non déclaré"`.

#### Objet `activitePrincipale`

| Champ JSON | Source CSV    | Transformation                              |
|------------|---------------|---------------------------------------------|
| id         | (généré)      | Auto-increment par code NAF unique          |
| code       | NAF2008_ETAB  | Tel quel                                    |
| libelle    | (table réf)   | Lookup dans la table NAF                    |

**Table NAF** : ~700 codes. Utiliser le fichier officiel INSEE des codes NAF rev2 (format CSV). Le fichier est disponible sur data.gouv.fr ou le site INSEE.

> Le service doit embarquer cette table en dur (fichier Go embedded ou fichier JSON chargé au démarrage).

#### Tableau `activiteSecondaires`

Même structure que `activitePrincipale`. Construire le tableau à partir des colonnes `NAF2008_ETAB_1` à `NAF2008_ETAB_5` :
- Ignorer les colonnes vides
- Chaque entrée non-vide génère un objet `{id, code, libelle}`

### 3.4 Règle de filtrage des établissements radiés

Le code Rails actuel filtre les établissements radiés :

```ruby
list_etablissements = data_source.sort_by { |a| a[:numEtablissement] }
                                 .filter { |h| h[:dateRadiation].nil? }
```

**Le filtrage n'est PAS fait côté service Go.** Le service retourne TOUS les établissements (y compris radiés). C'est le `PfEtablissementAdapter` côté Rails qui filtre.

### 3.5 Cas limites

| Cas | Comportement attendu |
|-----|---------------------|
| `numeroTahiti` non trouvé | Retourner `[]` (tableau vide) avec HTTP 200 |
| `numeroTahiti` manquant dans la query | HTTP 400 `{"error": "numeroTahiti parameter is required"}` |
| CSV non chargé / service démarrant | HTTP 503 `{"error": "service not ready"}` |
| Champ CSV vide | `null` dans le JSON (pas de chaîne vide `""`) |
| Champ ADRGEO contenant `""` (guillemets littéraux) | Traiter comme vide → `null` |

---

## 4. Endpoints secondaires

### 4.1 Health check

```
GET /healthz
```

Retourne HTTP 200 `{"status": "ok", "entries": 115602}` quand le CSV est chargé.
Retourne HTTP 503 `{"status": "loading"}` pendant le chargement initial.

### 4.2 Rechargement du CSV

```
POST /admin/reload
```

Recharge le CSV depuis `/data/exportrte.csv` sans redémarrage du service.
Retourne HTTP 200 `{"status": "reloaded", "entries": 115602}`.

Le rechargement doit être **atomique** : les requêtes en cours continuent de servir l'ancien index pendant que le nouveau se charge, puis on bascule.

---

## 5. Architecture du code Go

### 5.1 Structure du repo suggérée

```
pf-entreprise/
├── main.go                  # Point d'entrée, serveur HTTP, routes
├── csv.go                   # Parsing CSV, construction de l'index
├── models.go                # Structs Go pour le JSON de sortie
├── reference.go             # Tables de référence (effectifs, formes juridiques, NAF, communes)
├── handlers.go              # Handlers HTTP
├── reference_data/
│   ├── naf.json             # Codes NAF avec libellés
│   ├── formes_juridiques.json
│   ├── effectifs.json
│   └── communes_subdivisions.json
├── Dockerfile
├── go.mod
├── go.sum
├── README.md
└── main_test.go             # Tests
```

### 5.2 Dépendances

**Zéro dépendance externe.** Utiliser uniquement la stdlib Go :
- `net/http` pour le serveur
- `encoding/csv` pour le parsing
- `encoding/json` pour la sérialisation
- `sync` pour le rechargement atomique (`sync.RWMutex` ou `atomic.Value`)
- `embed` pour les fichiers de référence
- `log` pour le logging
- `golang.org/x/text/encoding/charmap` (seule exception : pour décoder Windows-1252 si nécessaire)

### 5.3 Index en mémoire

```go
// Structure principale : map[numeroTahiti] → []Etablissement
type DataStore struct {
    mu      sync.RWMutex
    index   map[string][]Etablissement
    count   int
    loaded  bool
}
```

Le CSV est regroupé par `Numtah` : chaque `numeroTahiti` peut avoir 1 à N établissements.

### 5.4 Gestion de l'encodage

Le CSV peut être en Windows-1252 (caractères accentués). Stratégie :
1. Essayer de lire en UTF-8
2. Si erreur de décodage, relire en Windows-1252 via `golang.org/x/text/encoding/charmap`
3. Logguer l'encodage détecté au démarrage

---

## 6. Docker

### 6.1 Dockerfile (multi-stage)

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /pf-entreprise .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=builder /pf-entreprise /pf-entreprise
EXPOSE 3000
CMD ["/pf-entreprise"]
```

### 6.2 Image cible
- **Registry** : `govpf/pf-entreprise`
- **Tag convention** : `latest` pour main, `vX.Y.Z` pour les releases
- **Taille cible** : < 30 Mo

---

## 7. Configuration

Le service se configure uniquement par variables d'environnement :

| Variable   | Default               | Description                         |
|------------|-----------------------|-------------------------------------|
| `PORT`     | `3000`                | Port d'écoute HTTP                  |
| `CSV_PATH` | `/data/exportrte.csv` | Chemin du fichier CSV               |
| `LOG_LEVEL`| `info`                | Niveau de log (debug, info, warn)   |

---

## 8. Tests

### 8.1 Tests unitaires à implémenter

1. **Parsing CSV** : vérifier qu'une ligne CSV est correctement parsée en struct
2. **Conversion de dates** : `DD/MM/YYYY` → `YYYY-MM-DD`, champs vides → `nil`
3. **Tables de référence** : lookup classe effectif, forme juridique, NAF, subdivision
4. **Index** : vérifier le regroupement par `Numtah`
5. **JSON output** : comparer la sortie avec un JSON i-taiete de référence

### 8.2 Données de test

Utiliser ces lignes CSV pour les tests :

```csv
Numtah;Nom_ENT;Sigle_ENT;code_Fjur;NAF2008_ENT;Classe_Effectifs;Code_Postal_ENT;BP_ENT;Com_BP_ENT;NumETA;NumtahETA;Nom_ETAB;Com_ETAB;Com_ETAB_libelle;PK;Quartier;Num_adr;Rue;Immeuble;ADRGEO;NAF2008_ETAB;NAF2008_ETAB_1;NAF2008_ETAB_2;NAF2008_ETAB_3;NAF2008_ETAB_4;NAF2008_ETAB_5;Insc_ENT;Mod_ENT;Rad_ENT;Reins_ENT;Insc_ETAB;Mod_ETAB;Rad_ETAB;Reins_ETAB
000026;HAUT-COMMISSARIAT DE LA REPUBLIQUE  ;HAUSSARIAT;710;8411Z;08;98713 PAPEETE BP;115;35000;001;000026-001;HAUT-COMMISSARIAT;35000;Papeete;;;;Avenue Bruat;;"";8411Z;8411Z;;;;;01/01/1991;01/09/2022;;;01/01/1991;11/08/2009;;
075390;BANQUE SOCREDO  ;SOCREDO;560;6419Z;08;98713 PAPEETE BP;130;35000;001;075390-001;SIEGE SOCIAL;35000;Papeete;;;;Avenue Pouvana a Oopa;;"";6419Z;6419Z;;;;;01/01/1991;01/09/2022;;;01/08/1987;24/07/2003;;
075390;BANQUE SOCREDO  ;SOCREDO;560;6419Z;08;98713 PAPEETE BP;130;35000;002;075390-002;AGENCE DE UTUROA;58000;Uturoa;;;;;;"Centre villeRaiatea";6419Z;6419Z;;;;;01/01/1991;01/09/2022;;;13/08/1987;24/07/2003;;
```

JSON attendu pour `?numeroTahiti=075390` : tableau de 2 établissements (001 et 002).
JSON attendu pour `?numeroTahiti=999999` : `[]`.

---

## 9. Déploiement K8s

Le chart Helm est déjà créé dans `kub-mes-demarches/charts/pf-entreprise/`. Le service sera déployé avec :

```bash
helm upgrade --install pf-entreprise ./charts/pf-entreprise -f ./charts/pf-entreprise/production.yaml
```

### 9.1 Communication avec mes-demarches

Le service est accessible en interne via DNS Kubernetes : `http://pf-entreprise:3000`

Dans `charts/mes-demarches/production.yaml`, il faudra remplacer le secret `gravitee` par une variable d'environnement directe :

```yaml
# Avant (secret gravitee) :
# API_ISPF_URL: (from secret gravitee/url)

# Après (service interne) :
API_ISPF_URL: http://pf-entreprise:3000
```

### 9.2 Mise à jour du CSV

Un CronJob K8s (défini dans le chart) télécharge le CSV quotidiennement à 04:00 :
1. `curl` télécharge le CSV depuis data.gouv.fr vers le PVC partagé
2. `curl -X POST http://pf-entreprise:3000/admin/reload` signale au service de recharger

### 9.3 Premier déploiement

Avant le premier déploiement, le CSV initial doit être copié sur le PVC :
```bash
# Depuis un pod dans le cluster
kubectl cp exportrte.csv <namespace>/<pf-entreprise-pod>:/data/exportrte.csv
```

Ou déclencher manuellement le CronJob :
```bash
kubectl create job --from=cronjob/pf-entreprise-csv-update pf-entreprise-csv-init
```

---

## 10. Checklist d'implémentation

- [ ] Initialiser le repo Go (`go mod init`)
- [ ] Implémenter le parsing CSV (`csv.go`)
- [ ] Implémenter les structs de sortie JSON (`models.go`)
- [ ] Embarquer les tables de référence (`reference.go` + `reference_data/`)
- [ ] Implémenter le handler principal (`handlers.go`)
- [ ] Implémenter `/healthz` et `/admin/reload`
- [ ] Écrire les tests unitaires (`main_test.go`)
- [ ] Créer le Dockerfile multi-stage
- [ ] Tester avec le vrai CSV `exportrte.csv`
- [ ] Comparer la sortie JSON avec une réponse i-taiete réelle
- [ ] Builder et pusher l'image vers `govpf/pf-entreprise`
- [ ] Déployer dans le cluster et tester l'intégration avec mes-demarches

---

## 11. Extraire les tables de référence

Pour constituer les fichiers `reference_data/*.json`, exécuter sur le CSV :

```bash
# Formes juridiques (codes uniques)
cut -d';' -f4 exportrte.csv | sort -u | tail -n +2

# Classes d'effectifs (codes uniques)
cut -d';' -f6 exportrte.csv | sort -u | tail -n +2

# Codes NAF (codes uniques)
cut -d';' -f21 exportrte.csv | sort -u | tail -n +2

# Communes et subdivisions (code + libellé uniques)
cut -d';' -f13,14 exportrte.csv | sort -u | tail -n +2
```

Les libellés correspondants devront être complétés manuellement ou depuis les sources officielles (INSEE pour NAF, ISPF pour le reste).
