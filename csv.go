package main

import (
	"bufio"
	"encoding/csv"
	"fmt"
	"io"
	"log"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"unicode/utf8"

	"golang.org/x/text/encoding/charmap"
)

// DataStore contient l'index en mémoire des établissements regroupés par Numtah.
type DataStore struct {
	mu     sync.RWMutex
	index  map[string][]Etablissement
	count  int
	loaded bool
}

// Lookup retourne les établissements pour un numéro TAHITI donné.
func (ds *DataStore) Lookup(numTahiti string) []Etablissement {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	if etabs, ok := ds.index[numTahiti]; ok {
		return etabs
	}
	return []Etablissement{}
}

// IsLoaded indique si le DataStore a terminé le chargement initial.
func (ds *DataStore) IsLoaded() bool {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return ds.loaded
}

// Count retourne le nombre total d'établissements chargés.
func (ds *DataStore) Count() int {
	ds.mu.RLock()
	defer ds.mu.RUnlock()
	return ds.count
}

// Reload recharge le CSV de manière atomique.
func (ds *DataStore) Reload(path string) error {
	newIndex, newCount, err := buildIndex(path)
	if err != nil {
		return err
	}
	ds.mu.Lock()
	ds.index = newIndex
	ds.count = newCount
	ds.loaded = true
	ds.mu.Unlock()
	return nil
}

// LoadCSV charge le CSV et retourne un DataStore prêt.
func LoadCSV(path string) (*DataStore, error) {
	index, count, err := buildIndex(path)
	if err != nil {
		return nil, err
	}
	return &DataStore{
		index:  index,
		count:  count,
		loaded: true,
	}, nil
}

func buildIndex(path string) (map[string][]Etablissement, int, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, 0, fmt.Errorf("impossible d'ouvrir le CSV: %w", err)
	}
	defer f.Close()

	reader, encoding := detectAndCreateReader(f)
	log.Printf("Encodage détecté: %s", encoding)

	csvReader := csv.NewReader(reader)
	csvReader.Comma = ';'
	csvReader.LazyQuotes = true

	// Lire et ignorer l'en-tête
	header, err := csvReader.Read()
	if err != nil {
		return nil, 0, fmt.Errorf("impossible de lire l'en-tête CSV: %w", err)
	}
	if len(header) < 34 {
		return nil, 0, fmt.Errorf("en-tête CSV invalide: %d colonnes (attendu 34)", len(header))
	}

	index := make(map[string][]Etablissement)
	entrepriseIDs := make(map[string]int)
	entrepriseNextID := 1
	entrepriseCache := make(map[string]*Entreprise) // numtah → Entreprise partagée
	communeNames := make(map[string]string)         // code commune → libellé
	communeCache := make(map[string]*CommuneGeo)    // code commune → CommuneGeo partagée
	etabID := 1
	lineNum := 1

	for {
		record, err := csvReader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			lineNum++
			log.Printf("WARNING: erreur ligne %d: %v", lineNum, err)
			continue
		}
		lineNum++

		if len(record) < 34 {
			log.Printf("WARNING: ligne %d ignorée: %d colonnes (attendu 34)", lineNum, len(record))
			continue
		}

		// Construire le mapping code commune → libellé
		if record[12] != "" && record[13] != "" {
			communeNames[record[12]] = record[13]
		}

		etab := parseRecord(record, etabID, entrepriseIDs, &entrepriseNextID, entrepriseCache, communeNames, communeCache)
		numtah := record[0]
		index[numtah] = append(index[numtah], etab)
		etabID++
	}

	// Trier les établissements par numEtablissement pour correspondre à l'ordre de i-taiete
	for numtah := range index {
		sort.Slice(index[numtah], func(i, j int) bool {
			return index[numtah][i].NumEtablissement < index[numtah][j].NumEtablissement
		})
	}

	totalEtabs := etabID - 1
	log.Printf("CSV chargé: %d établissements, %d entreprises uniques", totalEtabs, len(entrepriseIDs))
	return index, totalEtabs, nil
}

func parseRecord(record []string, etabID int, entrepriseIDs map[string]int, entrepriseNextID *int, entrepriseCache map[string]*Entreprise, communeNames map[string]string, communeCache map[string]*CommuneGeo) Etablissement {
	numtah := record[0]

	// Réutiliser l'Entreprise existante ou en créer une nouvelle
	ent, entExists := entrepriseCache[numtah]
	if !entExists {
		// Obtenir ou créer l'ID entreprise
		entID, ok := entrepriseIDs[numtah]
		if !ok {
			entID = *entrepriseNextID
			entrepriseIDs[numtah] = entID
			*entrepriseNextID++
		}

		// Construire la commune entreprise (depuis Com_BP_ENT, col 8)
		entCommune := lookupOrCreateCommune(record[8], communeNames, communeCache)

		ent = &Entreprise{
			ID:                 entID,
			NumeroTahiti:       numtah,
			RaisonSociale:      nullableTrimmedString(record[1]),
			Sigle:              nullableString(record[2]),
			ClasseEffectif:     LookupEffectif(record[5]),
			FormeJuridique:     LookupFormeJuridique(record[3]),
			ActivitePrincipale: LookupNAF(record[4]),
			Commune:            entCommune,
			Email:              nil,
			Telephone:          nil,
			AdressePostale:     nullableString(record[6]),
			BoitePostale:       stripLeadingZeros(record[7]),
			DateInscription:    convertDate(record[26]),
			DateModification:   convertDate(record[27]),
			DateRadiation:      convertDate(record[28]),
			DateReinscription:  convertDate(record[29]),
			Version:            nil,
		}
		entrepriseCache[numtah] = ent
	}

	// Parser NumETA en entier
	numETA := parseIntField(record[9])

	// Parser les activités NAF
	activitePrincipale := LookupNAF(record[20])
	activiteSecondaires := buildActiviteSecondaires(record[21:26])

	// Parser la commune établissement (avec cache)
	communeGeo := lookupOrCreateCommune(record[12], communeNames, communeCache)

	// Concaténer Num_adr + Rue (comme i-taiete)
	rue := buildRue(record[16], record[17])

	return Etablissement{
		ID:                  etabID,
		Entreprise:          ent,
		NumEtablissement:    numETA,
		NomCommercial:       nullableTrimmedString(record[11]),
		BoitePostale:        nil,
		AdressePostale:      nil,
		Telephone:           nil,
		Fax:                 nil,
		PointKilometrique:   nullableString(record[14]),
		Quartier:            nullableString(record[15]),
		AdresseGeo:          nullableADRGEO(record[19]),
		CommuneGeo:          communeGeo,
		Rue:                 rue,
		Immeuble:            nullableString(record[18]),
		ActivitePrincipale:  activitePrincipale,
		ActiviteSecondaires: activiteSecondaires,
		DateInscription:     convertDate(record[30]),
		DateModification:    convertDate(record[31]),
		DateRadiation:       convertDate(record[32]),
		DateReinscription:   convertDate(record[33]),
		Version:             nil,
	}
}

// lookupOrCreateCommune retourne un *CommuneGeo depuis le cache ou en crée un nouveau.
func lookupOrCreateCommune(codeCommune string, communeNames map[string]string, communeCache map[string]*CommuneGeo) *CommuneGeo {
	if codeCommune == "" {
		return nil
	}
	if cached, ok := communeCache[codeCommune]; ok {
		return cached
	}
	subdivLibelle := LookupSubdivision(codeCommune)
	subdivID := GetSubdivisionID(subdivLibelle)

	// Priorité à la table de référence communes.json
	communeAssociee, communeMere := LookupCommune(codeCommune)
	if communeAssociee == "" {
		// Fallback CSV pour codes inconnus
		nom := communeNames[codeCommune]
		communeAssociee = nom
		communeMere = nom
	}

	cg := &CommuneGeo{
		ID:              GetCommuneID(codeCommune),
		CommuneAssociee: communeAssociee,
		CommuneMere:     communeMere,
		Subdivision: &Subdivision{
			ID:      subdivID,
			Libelle: subdivLibelle,
		},
		ChampImport: parseIntField(codeCommune),
	}
	communeCache[codeCommune] = cg
	return cg
}

func buildActiviteSecondaires(codes []string) []*ActiviteNAF {
	var result []*ActiviteNAF
	for _, code := range codes {
		if code == "" {
			continue
		}
		naf := LookupNAF(code)
		if naf != nil {
			result = append(result, naf)
		}
	}
	if result == nil {
		return []*ActiviteNAF{}
	}
	return result
}

// nullableString retourne nil si la chaîne est vide, sinon un pointeur vers la chaîne.
func nullableString(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// nullableTrimmedString retourne nil si vide, sinon un pointeur vers la chaîne trimmée.
func nullableTrimmedString(s string) *string {
	s = strings.TrimRight(s, " ")
	if s == "" {
		return nil
	}
	return &s
}

// buildRue concatène Num_adr et Rue comme i-taiete (ex: "115" + "Dumont d'Urville" → "115 Dumont d'Urville").
func buildRue(numAdr, rue string) *string {
	numAdr = strings.TrimSpace(numAdr)
	rue = strings.TrimSpace(rue)
	if numAdr == "" && rue == "" {
		return nil
	}
	if numAdr == "" {
		return &rue
	}
	if rue == "" {
		return &numAdr
	}
	result := numAdr + " " + rue
	return &result
}

// stripLeadingZeros retire les zéros initiaux d'une chaîne numérique ("004900" → "4900").
func stripLeadingZeros(s string) *string {
	if s == "" {
		return nil
	}
	trimmed := strings.TrimLeft(s, "0")
	if trimmed == "" {
		trimmed = "0"
	}
	return &trimmed
}

// nullableADRGEO traite le champ ADRGEO : les guillemets littéraux "" sont considérés comme vide.
func nullableADRGEO(s string) *string {
	if s == "" || s == `""` {
		return nil
	}
	return &s
}

// convertDate convertit une date DD/MM/YYYY en YYYY-MM-DD. Retourne nil si vide.
func convertDate(s string) *string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, "/")
	if len(parts) != 3 {
		log.Printf("WARNING: format de date invalide: %q", s)
		return &s
	}
	result := parts[2] + "-" + parts[1] + "-" + parts[0]
	return &result
}

// parseIntField parse une chaîne en entier (ex: "001" → 1, "35000" → 35000).
func parseIntField(s string) int {
	if s == "" {
		return 0
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		log.Printf("WARNING: impossible de parser en entier: %q", s)
		return 0
	}
	return n
}

// detectAndCreateReader détecte l'encodage du fichier et retourne un reader approprié.
func detectAndCreateReader(f *os.File) (io.Reader, string) {
	// Lire les premiers octets pour détecter l'encodage
	buf := make([]byte, 4096)
	n, err := f.Read(buf)
	if err != nil {
		log.Printf("WARNING: impossible de lire le début du fichier: %v", err)
		f.Seek(0, 0)
		return bufio.NewReader(f), "UTF-8 (défaut)"
	}

	// Remettre le curseur au début
	f.Seek(0, 0)

	if utf8.Valid(buf[:n]) {
		return bufio.NewReader(f), "UTF-8"
	}

	// Fallback Windows-1252
	decoder := charmap.Windows1252.NewDecoder()
	return decoder.Reader(f), "Windows-1252"
}
