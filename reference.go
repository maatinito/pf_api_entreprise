package main

import (
	"embed"
	"encoding/json"
	"log"
	"strings"
	"sync"
)

//go:embed reference_data
var referenceFS embed.FS

var (
	effectifsMap            map[string]string
	formesJuridiquesMap     map[string]string
	nafMap                  map[string]string
	communesSubdivisionsMap map[string]string

	// Auto-increment IDs par type de référence
	formeJuridiqueIDs    map[string]int
	formeJuridiqueMu     sync.Mutex
	formeJuridiqueNextID int = 1

	nafIDs    map[string]int
	nafMu     sync.Mutex
	nafNextID int = 1

	communeIDs    map[string]int
	communeMu     sync.Mutex
	communeNextID int = 1

	subdivisionIDs    map[string]int
	subdivisionMu     sync.Mutex
	subdivisionNextID int = 1

	// Caches pour les objets de référence (évite les allocations dupliquées)
	effectifCache        map[string]*ClasseEffectif
	formeJuridiqueCache  map[string]*FormeJuridique
	nafCache             map[string]*ActiviteNAF
)

func initReferences() {
	effectifsMap = loadJSONMap("reference_data/effectifs.json")
	formesJuridiquesMap = loadJSONMap("reference_data/formes_juridiques.json")
	nafMap = loadJSONMap("reference_data/naf.json")
	communesSubdivisionsMap = loadJSONMap("reference_data/communes_subdivisions.json")

	formeJuridiqueIDs = make(map[string]int)
	nafIDs = make(map[string]int)
	communeIDs = make(map[string]int)
	subdivisionIDs = make(map[string]int)

	effectifCache = make(map[string]*ClasseEffectif)
	formeJuridiqueCache = make(map[string]*FormeJuridique)
	nafCache = make(map[string]*ActiviteNAF)
}

func loadJSONMap(path string) map[string]string {
	data, err := referenceFS.ReadFile(path)
	if err != nil {
		log.Fatalf("Impossible de charger %s: %v", path, err)
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		log.Fatalf("Impossible de parser %s: %v", path, err)
	}
	return m
}

// LookupEffectif retourne la ClasseEffectif pour un code donné (ex: "08").
// Le code est converti en entier pour l'ID (ex: "08" → 8).
func LookupEffectif(code string) *ClasseEffectif {
	if code == "" {
		return nil
	}
	if cached, ok := effectifCache[code]; ok {
		return cached
	}
	libelle, ok := effectifsMap[code]
	if !ok {
		log.Printf("WARNING: code effectif inconnu: %q", code)
		return nil
	}
	id := parseIntFromCode(code)
	ce := &ClasseEffectif{ID: id, Libelle: libelle}
	effectifCache[code] = ce
	return ce
}

// LookupFormeJuridique retourne la FormeJuridique pour un code donné.
func LookupFormeJuridique(code string) *FormeJuridique {
	if code == "" {
		return nil
	}
	if cached, ok := formeJuridiqueCache[code]; ok {
		return cached
	}
	libelle, ok := formesJuridiquesMap[code]
	if !ok {
		log.Printf("WARNING: code forme juridique inconnu: %q", code)
		libelle = "Forme juridique inconnue (" + code + ")"
	}
	id := getFormeJuridiqueID(code)
	fj := &FormeJuridique{ID: id, Code: code, Libelle: libelle}
	formeJuridiqueCache[code] = fj
	return fj
}

// LookupNAF retourne l'ActiviteNAF pour un code donné.
func LookupNAF(code string) *ActiviteNAF {
	if code == "" {
		return nil
	}
	if cached, ok := nafCache[code]; ok {
		return cached
	}
	libelle, ok := nafMap[code]
	if !ok {
		log.Printf("WARNING: code NAF inconnu: %q", code)
		libelle = "Activité inconnue (" + code + ")"
	}
	id := getNAFID(code)
	naf := &ActiviteNAF{ID: id, Code: code, Libelle: libelle}
	nafCache[code] = naf
	return naf
}

// LookupSubdivision retourne le libellé de subdivision pour un code commune.
func LookupSubdivision(codeCommune string) string {
	if len(codeCommune) < 2 {
		return "Non déclaré"
	}
	prefix := codeCommune[:2]
	if libelle, ok := communesSubdivisionsMap[prefix]; ok {
		return libelle
	}
	log.Printf("WARNING: préfixe commune inconnu: %q (code: %s)", prefix, codeCommune)
	return "Non déclaré"
}

// GetCommuneID retourne un ID auto-incrémenté stable pour un code commune.
func GetCommuneID(codeCommune string) int {
	communeMu.Lock()
	defer communeMu.Unlock()
	if id, ok := communeIDs[codeCommune]; ok {
		return id
	}
	id := communeNextID
	communeIDs[codeCommune] = id
	communeNextID++
	return id
}

// GetSubdivisionID retourne un ID auto-incrémenté stable pour une subdivision.
func GetSubdivisionID(libelle string) int {
	subdivisionMu.Lock()
	defer subdivisionMu.Unlock()
	if id, ok := subdivisionIDs[libelle]; ok {
		return id
	}
	id := subdivisionNextID
	subdivisionIDs[libelle] = id
	subdivisionNextID++
	return id
}

func getFormeJuridiqueID(code string) int {
	formeJuridiqueMu.Lock()
	defer formeJuridiqueMu.Unlock()
	if id, ok := formeJuridiqueIDs[code]; ok {
		return id
	}
	id := formeJuridiqueNextID
	formeJuridiqueIDs[code] = id
	formeJuridiqueNextID++
	return id
}

func getNAFID(code string) int {
	nafMu.Lock()
	defer nafMu.Unlock()
	if id, ok := nafIDs[code]; ok {
		return id
	}
	id := nafNextID
	nafIDs[code] = id
	nafNextID++
	return id
}

func parseIntFromCode(code string) int {
	code = strings.TrimLeft(code, "0")
	if code == "" {
		return 0
	}
	n := 0
	for _, c := range code {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		}
	}
	return n
}
