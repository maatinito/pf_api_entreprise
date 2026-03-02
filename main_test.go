package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

const testCSVContent = `Numtah;Nom_ENT;Sigle_ENT;code_Fjur;NAF2008_ENT;Classe_Effectifs;Code_Postal_ENT;BP_ENT;Com_BP_ENT;NumETA;NumtahETA;Nom_ETAB;Com_ETAB;Com_ETAB_libelle;PK;Quartier;Num_adr;Rue;Immeuble;ADRGEO;NAF2008_ETAB;NAF2008_ETAB_1;NAF2008_ETAB_2;NAF2008_ETAB_3;NAF2008_ETAB_4;NAF2008_ETAB_5;Insc_ENT;Mod_ENT;Rad_ENT;Reins_ENT;Insc_ETAB;Mod_ETAB;Rad_ETAB;Reins_ETAB
000026;HAUT-COMMISSARIAT DE LA REPUBLIQUE  ;HAUSSARIAT;710;8411Z;08;98713 PAPEETE BP;115;35000;001;000026-001;HAUT-COMMISSARIAT;35000;Papeete;;;;Avenue Bruat;;"";8411Z;8411Z;;;;;01/01/1991;01/09/2022;;;01/01/1991;11/08/2009;;
075390;BANQUE SOCREDO  ;SOCREDO;560;6419Z;08;98713 PAPEETE BP;130;35000;001;075390-001;SIEGE SOCIAL;35000;Papeete;;;;Avenue Pouvana a Oopa;;"";6419Z;6419Z;;;;;01/01/1991;01/09/2022;;;01/08/1987;24/07/2003;;
075390;BANQUE SOCREDO  ;SOCREDO;560;6419Z;08;98713 PAPEETE BP;130;35000;002;075390-002;AGENCE DE UTUROA;58000;Uturoa;;;;;;"Centre villeRaiatea";6419Z;6419Z;;;;;01/01/1991;01/09/2022;;;13/08/1987;24/07/2003;;
`

func createTestCSV(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, "test.csv")
	if err := os.WriteFile(path, []byte(testCSVContent), 0644); err != nil {
		t.Fatalf("Impossible de créer le CSV de test: %v", err)
	}
	return path
}

func loadTestStore(t *testing.T) *DataStore {
	t.Helper()
	initReferences()
	path := createTestCSV(t)
	store, err := LoadCSV(path)
	if err != nil {
		t.Fatalf("Impossible de charger le CSV de test: %v", err)
	}
	return store
}

// --- Tests de conversion de dates ---

func TestConvertDate(t *testing.T) {
	tests := []struct {
		input    string
		expected *string
	}{
		{"01/01/1991", strPtr("1991-01-01")},
		{"13/08/1987", strPtr("1987-08-13")},
		{"24/07/2003", strPtr("2003-07-24")},
		{"01/09/2022", strPtr("2022-09-01")},
		{"11/08/2009", strPtr("2009-08-11")},
		{"", nil},
	}

	for _, tt := range tests {
		result := convertDate(tt.input)
		if tt.expected == nil {
			if result != nil {
				t.Errorf("convertDate(%q) = %q, attendu nil", tt.input, *result)
			}
		} else {
			if result == nil {
				t.Errorf("convertDate(%q) = nil, attendu %q", tt.input, *tt.expected)
			} else if *result != *tt.expected {
				t.Errorf("convertDate(%q) = %q, attendu %q", tt.input, *result, *tt.expected)
			}
		}
	}
}

// --- Tests de nullableString et nullableADRGEO ---

func TestNullableString(t *testing.T) {
	if nullableString("") != nil {
		t.Error("nullableString(\"\") devrait retourner nil")
	}
	result := nullableString("test")
	if result == nil || *result != "test" {
		t.Error("nullableString(\"test\") devrait retourner un pointeur vers \"test\"")
	}
}

func TestNullableADRGEO(t *testing.T) {
	if nullableADRGEO("") != nil {
		t.Error("nullableADRGEO(\"\") devrait retourner nil")
	}
	if nullableADRGEO(`""`) != nil {
		t.Error(`nullableADRGEO("\"\"") devrait retourner nil`)
	}
	result := nullableADRGEO("Centre villeRaiatea")
	if result == nil || *result != "Centre villeRaiatea" {
		t.Error("nullableADRGEO(\"Centre villeRaiatea\") devrait retourner un pointeur")
	}
}

// --- Tests des tables de référence ---

func TestLookupEffectif(t *testing.T) {
	initReferences()

	tests := []struct {
		code          string
		expectedID    int
		expectedLabel string
		expectedNil   bool
	}{
		{"08", 8, "200 à 499 personnes", false},
		{"00", 0, "Aucune personne", false},
		{"13", 13, "10000 personnes et plus", false},
		{"", 0, "", true},
	}

	for _, tt := range tests {
		result := LookupEffectif(tt.code)
		if tt.expectedNil {
			if result != nil {
				t.Errorf("LookupEffectif(%q) devrait retourner nil", tt.code)
			}
			continue
		}
		if result == nil {
			t.Errorf("LookupEffectif(%q) a retourné nil", tt.code)
			continue
		}
		if result.ID != tt.expectedID {
			t.Errorf("LookupEffectif(%q).ID = %d, attendu %d", tt.code, result.ID, tt.expectedID)
		}
		if result.Libelle != tt.expectedLabel {
			t.Errorf("LookupEffectif(%q).Libelle = %q, attendu %q", tt.code, result.Libelle, tt.expectedLabel)
		}
	}
}

func TestLookupFormeJuridique(t *testing.T) {
	initReferences()

	result := LookupFormeJuridique("560")
	if result == nil {
		t.Fatal("LookupFormeJuridique(\"560\") a retourné nil")
	}
	if result.Code != "560" {
		t.Errorf("Code = %q, attendu \"560\"", result.Code)
	}
	if result.Libelle != "Société Anonyme à Directoire (dont S.A.E.M.)" {
		t.Errorf("Libelle = %q, attendu \"Société Anonyme à Directoire (dont S.A.E.M.)\"", result.Libelle)
	}

	resultNil := LookupFormeJuridique("")
	if resultNil != nil {
		t.Error("LookupFormeJuridique(\"\") devrait retourner nil")
	}
}

func TestLookupNAF(t *testing.T) {
	initReferences()

	result := LookupNAF("6419Z")
	if result == nil {
		t.Fatal("LookupNAF(\"6419Z\") a retourné nil")
	}
	if result.Code != "6419Z" {
		t.Errorf("Code = %q, attendu \"6419Z\"", result.Code)
	}

	resultNil := LookupNAF("")
	if resultNil != nil {
		t.Error("LookupNAF(\"\") devrait retourner nil")
	}
}

func TestLookupSubdivision(t *testing.T) {
	initReferences()

	tests := []struct {
		code     string
		expected string
	}{
		{"35000", "Iles Du Vent"},
		{"38000", "Iles Du Vent"},
		{"29400", "Iles Du Vent"},
		{"58000", "Iles Sous-Le-Vent"},
		{"24200", "Iles Sous-Le-Vent"},
		{"11100", "Tuamotu-Gambier"},
		{"19000", "Tuamotu-Gambier"},
		{"31200", "Marquises"},
		{"18000", "Marquises"},
		{"44100", "Australes"},
		{"53200", "Australes"},
		{"99000", "Non déclaré"},
		{"", "Non déclaré"},
	}

	for _, tt := range tests {
		result := LookupSubdivision(tt.code)
		if result != tt.expected {
			t.Errorf("LookupSubdivision(%q) = %q, attendu %q", tt.code, result, tt.expected)
		}
	}
}

// --- Tests du parsing CSV et de l'index ---

func TestLoadCSV(t *testing.T) {
	store := loadTestStore(t)

	if store.Count() != 3 {
		t.Errorf("Count = %d, attendu 3", store.Count())
	}
	if !store.IsLoaded() {
		t.Error("IsLoaded devrait retourner true")
	}
}

func TestIndexGrouping(t *testing.T) {
	store := loadTestStore(t)

	// 075390 devrait avoir 2 établissements
	etabs := store.Lookup("075390")
	if len(etabs) != 2 {
		t.Fatalf("075390 devrait avoir 2 établissements, trouvé %d", len(etabs))
	}

	// 000026 devrait avoir 1 établissement
	etabs026 := store.Lookup("000026")
	if len(etabs026) != 1 {
		t.Fatalf("000026 devrait avoir 1 établissement, trouvé %d", len(etabs026))
	}

	// 999999 devrait retourner un tableau vide
	etabs999 := store.Lookup("999999")
	if len(etabs999) != 0 {
		t.Errorf("999999 devrait retourner 0 établissements, trouvé %d", len(etabs999))
	}
}

func TestParseRecord_Etablissement000026(t *testing.T) {
	store := loadTestStore(t)
	etabs := store.Lookup("000026")
	if len(etabs) != 1 {
		t.Fatalf("Attendu 1 établissement pour 000026, trouvé %d", len(etabs))
	}

	etab := etabs[0]

	// NumEtablissement: "001" → 1
	if etab.NumEtablissement != 1 {
		t.Errorf("NumEtablissement = %d, attendu 1", etab.NumEtablissement)
	}

	// NomCommercial
	if etab.NomCommercial == nil || *etab.NomCommercial != "HAUT-COMMISSARIAT" {
		t.Errorf("NomCommercial = %v, attendu \"HAUT-COMMISSARIAT\"", etab.NomCommercial)
	}

	// ADRGEO contenant "" → null
	if etab.AdresseGeo != nil {
		t.Errorf("AdresseGeo devrait être nil (ADRGEO=\"\"\"), trouvé %q", *etab.AdresseGeo)
	}

	// Dates
	if etab.DateInscription == nil || *etab.DateInscription != "1991-01-01" {
		t.Errorf("DateInscription = %v, attendu \"1991-01-01\"", etab.DateInscription)
	}
	if etab.DateModification == nil || *etab.DateModification != "2009-08-11" {
		t.Errorf("DateModification = %v, attendu \"2009-08-11\"", etab.DateModification)
	}
	if etab.DateRadiation != nil {
		t.Errorf("DateRadiation devrait être nil, trouvé %q", *etab.DateRadiation)
	}
	if etab.DateReinscription != nil {
		t.Errorf("DateReinscription devrait être nil, trouvé %q", *etab.DateReinscription)
	}

	// Rue (Num_adr vide + "Avenue Bruat" → "Avenue Bruat")
	if etab.Rue == nil || *etab.Rue != "Avenue Bruat" {
		t.Errorf("Rue = %v, attendu \"Avenue Bruat\"", etab.Rue)
	}

	// BoitePostale dupliquée depuis l'entreprise (comme i-taiete)
	if etab.BoitePostale == nil || *etab.BoitePostale != "115" {
		t.Errorf("BoitePostale = %v, attendu \"115\"", etab.BoitePostale)
	}
	if etab.Telephone != nil {
		t.Error("Telephone devrait être nil")
	}
	if etab.Version != nil {
		t.Error("Version devrait être nil")
	}
}

func TestParseRecord_Entreprise(t *testing.T) {
	store := loadTestStore(t)
	etabs := store.Lookup("000026")
	ent := etabs[0].Entreprise

	if ent.NumeroTahiti != "000026" {
		t.Errorf("NumeroTahiti = %q, attendu \"000026\"", ent.NumeroTahiti)
	}

	// RaisonSociale avec espaces trailing trimmés (comme i-taiete)
	if ent.RaisonSociale == nil || *ent.RaisonSociale != "HAUT-COMMISSARIAT DE LA REPUBLIQUE" {
		t.Errorf("RaisonSociale = %v, attendu \"HAUT-COMMISSARIAT DE LA REPUBLIQUE\"", ent.RaisonSociale)
	}

	if ent.Sigle == nil || *ent.Sigle != "HAUSSARIAT" {
		t.Errorf("Sigle = %v, attendu \"HAUSSARIAT\"", ent.Sigle)
	}

	// FormeJuridique
	if ent.FormeJuridique == nil {
		t.Fatal("FormeJuridique devrait ne pas être nil")
	}
	if ent.FormeJuridique.Code != "710" {
		t.Errorf("FormeJuridique.Code = %q, attendu \"710\"", ent.FormeJuridique.Code)
	}

	// ClasseEffectif
	if ent.ClasseEffectif == nil {
		t.Fatal("ClasseEffectif devrait ne pas être nil")
	}
	if ent.ClasseEffectif.ID != 8 {
		t.Errorf("ClasseEffectif.ID = %d, attendu 8", ent.ClasseEffectif.ID)
	}
	if ent.ClasseEffectif.Libelle != "200 à 499 personnes" {
		t.Errorf("ClasseEffectif.Libelle = %q, attendu \"200 à 499 personnes\"", ent.ClasseEffectif.Libelle)
	}

	// AdressePostale
	if ent.AdressePostale == nil || *ent.AdressePostale != "98713 PAPEETE BP" {
		t.Errorf("AdressePostale = %v, attendu \"98713 PAPEETE BP\"", ent.AdressePostale)
	}

	// BoitePostale
	if ent.BoitePostale == nil || *ent.BoitePostale != "115" {
		t.Errorf("BoitePostale = %v, attendu \"115\"", ent.BoitePostale)
	}

	// ActivitePrincipale entreprise (NAF2008_ENT)
	if ent.ActivitePrincipale == nil {
		t.Fatal("Entreprise.ActivitePrincipale devrait ne pas être nil")
	}
	if ent.ActivitePrincipale.Code != "8411Z" {
		t.Errorf("Entreprise.ActivitePrincipale.Code = %q, attendu \"8411Z\"", ent.ActivitePrincipale.Code)
	}

	// Commune entreprise (depuis Com_BP_ENT)
	if ent.Commune == nil {
		t.Fatal("Entreprise.Commune devrait ne pas être nil")
	}
	if ent.Commune.ChampImport != 35000 {
		t.Errorf("Entreprise.Commune.ChampImport = %d, attendu 35000", ent.Commune.ChampImport)
	}

	// Dates entreprise
	if ent.DateInscription == nil || *ent.DateInscription != "1991-01-01" {
		t.Errorf("Entreprise.DateInscription = %v, attendu \"1991-01-01\"", ent.DateInscription)
	}
	if ent.DateModification == nil || *ent.DateModification != "2022-09-01" {
		t.Errorf("Entreprise.DateModification = %v, attendu \"2022-09-01\"", ent.DateModification)
	}

	// Email et Version = nil
	if ent.Email != nil {
		t.Error("Email devrait être nil")
	}
	if ent.Version != nil {
		t.Error("Version devrait être nil")
	}
}

func TestParseRecord_CommuneGeo(t *testing.T) {
	store := loadTestStore(t)
	etabs := store.Lookup("075390")

	// Établissement 002 (AGENCE DE UTUROA) → commune 58000 → Iles Sous-Le-Vent
	var etabUturoa *Etablissement
	for i := range etabs {
		if etabs[i].NumEtablissement == 2 {
			etabUturoa = &etabs[i]
			break
		}
	}
	if etabUturoa == nil {
		t.Fatal("Établissement 002 non trouvé")
	}

	cg := etabUturoa.CommuneGeo
	if cg == nil {
		t.Fatal("CommuneGeo devrait ne pas être nil")
	}
	if cg.CommuneAssociee != "Uturoa" {
		t.Errorf("CommuneAssociee = %q, attendu \"Uturoa\"", cg.CommuneAssociee)
	}
	if cg.CommuneMere != "Uturoa" {
		t.Errorf("CommuneMere = %q, attendu \"Uturoa\"", cg.CommuneMere)
	}
	if cg.ChampImport != 58000 {
		t.Errorf("ChampImport = %d, attendu 58000", cg.ChampImport)
	}
	if cg.Subdivision == nil {
		t.Fatal("Subdivision devrait ne pas être nil")
	}
	if cg.Subdivision.Libelle != "Iles Sous-Le-Vent" {
		t.Errorf("Subdivision.Libelle = %q, attendu \"Iles Sous-Le-Vent\"", cg.Subdivision.Libelle)
	}

	// AdresseGeo = "Centre villeRaiatea" (non vide et non "")
	if etabUturoa.AdresseGeo == nil || *etabUturoa.AdresseGeo != "Centre villeRaiatea" {
		t.Errorf("AdresseGeo = %v, attendu \"Centre villeRaiatea\"", etabUturoa.AdresseGeo)
	}
}

func TestParseRecord_ActivitesNAF(t *testing.T) {
	store := loadTestStore(t)
	etabs := store.Lookup("075390")
	etab := etabs[0]

	if etab.ActivitePrincipale == nil {
		t.Fatal("ActivitePrincipale devrait ne pas être nil")
	}
	if etab.ActivitePrincipale.Code != "6419Z" {
		t.Errorf("ActivitePrincipale.Code = %q, attendu \"6419Z\"", etab.ActivitePrincipale.Code)
	}

	// ActiviteSecondaires: NAF2008_ETAB_1 = "6419Z", les autres sont vides → 1 activité secondaire
	if len(etab.ActiviteSecondaires) != 1 {
		t.Errorf("ActiviteSecondaires devrait avoir 1 élément, trouvé %d", len(etab.ActiviteSecondaires))
	}
	if len(etab.ActiviteSecondaires) > 0 && etab.ActiviteSecondaires[0].Code != "6419Z" {
		t.Errorf("ActiviteSecondaires[0].Code = %q, attendu \"6419Z\"", etab.ActiviteSecondaires[0].Code)
	}
}

// --- Tests des handlers HTTP ---

func TestHandleEtablissements_Found(t *testing.T) {
	store := loadTestStore(t)
	handler := HandleEtablissements(store)

	req := httptest.NewRequest("GET", "/etablissements/Entreprise?numeroTahiti=075390", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusOK)
	}

	contentType := w.Header().Get("Content-Type")
	if contentType != "application/json; charset=utf-8" {
		t.Errorf("Content-Type = %q, attendu \"application/json; charset=utf-8\"", contentType)
	}

	var etabs []Etablissement
	if err := json.Unmarshal(w.Body.Bytes(), &etabs); err != nil {
		t.Fatalf("Impossible de parser le JSON: %v", err)
	}
	if len(etabs) != 2 {
		t.Errorf("Attendu 2 établissements, trouvé %d", len(etabs))
	}
}

func TestHandleEtablissements_NotFound(t *testing.T) {
	store := loadTestStore(t)
	handler := HandleEtablissements(store)

	req := httptest.NewRequest("GET", "/etablissements/Entreprise?numeroTahiti=999999", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusOK)
	}

	var etabs []Etablissement
	if err := json.Unmarshal(w.Body.Bytes(), &etabs); err != nil {
		t.Fatalf("Impossible de parser le JSON: %v", err)
	}
	if len(etabs) != 0 {
		t.Errorf("Attendu 0 établissements, trouvé %d", len(etabs))
	}
}

func TestHandleEtablissements_MissingParam(t *testing.T) {
	store := loadTestStore(t)
	handler := HandleEtablissements(store)

	req := httptest.NewRequest("GET", "/etablissements/Entreprise", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusBadRequest)
	}

	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "numeroTahiti parameter is required" {
		t.Errorf("error = %q, attendu \"numeroTahiti parameter is required\"", resp["error"])
	}
}

func TestHandleEtablissements_ServiceNotReady(t *testing.T) {
	store := &DataStore{}
	handler := HandleEtablissements(store)

	req := httptest.NewRequest("GET", "/etablissements/Entreprise?numeroTahiti=075390", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusServiceUnavailable)
	}

	var resp map[string]string
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["error"] != "service not ready" {
		t.Errorf("error = %q, attendu \"service not ready\"", resp["error"])
	}
}

func TestHandleHealthz_Loaded(t *testing.T) {
	store := loadTestStore(t)
	handler := HandleHealthz(store)

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusOK)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["status"] != "ok" {
		t.Errorf("status = %v, attendu \"ok\"", resp["status"])
	}
	if int(resp["entries"].(float64)) != 3 {
		t.Errorf("entries = %v, attendu 3", resp["entries"])
	}
}

func TestHandleHealthz_NotLoaded(t *testing.T) {
	store := &DataStore{}
	handler := HandleHealthz(store)

	req := httptest.NewRequest("GET", "/healthz", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusServiceUnavailable {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusServiceUnavailable)
	}
}

func TestHandleReload(t *testing.T) {
	store := loadTestStore(t)
	csvPath := createTestCSV(t)
	handler := HandleReload(store, csvPath)

	req := httptest.NewRequest("POST", "/admin/reload", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusOK)
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["status"] != "reloaded" {
		t.Errorf("status = %v, attendu \"reloaded\"", resp["status"])
	}
}

func TestHandleReload_WrongMethod(t *testing.T) {
	store := loadTestStore(t)
	handler := HandleReload(store, "")

	req := httptest.NewRequest("GET", "/admin/reload", nil)
	w := httptest.NewRecorder()
	handler(w, req)

	if w.Code != http.StatusMethodNotAllowed {
		t.Errorf("Status = %d, attendu %d", w.Code, http.StatusMethodNotAllowed)
	}
}

// --- Test de la sérialisation JSON complète ---

func TestJSONOutput_NullFields(t *testing.T) {
	store := loadTestStore(t)
	etabs := store.Lookup("000026")
	etab := etabs[0]

	data, err := json.Marshal(etab)
	if err != nil {
		t.Fatalf("Impossible de sérialiser: %v", err)
	}

	var raw map[string]interface{}
	json.Unmarshal(data, &raw)

	// Vérifier que les champs null sont bien null (pas absents)
	nullFields := []string{"telephone", "fax",
		"pointKilometrique", "quartier", "adresseGeo", "immeuble",
		"dateRadiation", "dateReinscription", "version"}

	for _, field := range nullFields {
		val, exists := raw[field]
		if !exists {
			t.Errorf("Champ %q absent du JSON", field)
		} else if val != nil {
			t.Errorf("Champ %q = %v, attendu null", field, val)
		}
	}
}

func TestJSONOutput_ActiviteSecondairesEmptyArray(t *testing.T) {
	// Construire un établissement sans activités secondaires
	initReferences()

	etab := Etablissement{
		ActiviteSecondaires: []*ActiviteNAF{},
	}

	data, err := json.Marshal(etab)
	if err != nil {
		t.Fatalf("Impossible de sérialiser: %v", err)
	}

	var raw map[string]interface{}
	json.Unmarshal(data, &raw)

	// activiteSecondaires devrait être [] (pas null)
	secondaires, ok := raw["activiteSecondaires"].([]interface{})
	if !ok {
		t.Error("activiteSecondaires devrait être un tableau")
	} else if len(secondaires) != 0 {
		t.Errorf("activiteSecondaires devrait être vide, trouvé %d éléments", len(secondaires))
	}
}

// --- Test parseIntField ---

func TestParseIntField(t *testing.T) {
	tests := []struct {
		input    string
		expected int
	}{
		{"001", 1},
		{"35000", 35000},
		{"58000", 58000},
		{"", 0},
		{"002", 2},
	}

	for _, tt := range tests {
		result := parseIntField(tt.input)
		if result != tt.expected {
			t.Errorf("parseIntField(%q) = %d, attendu %d", tt.input, result, tt.expected)
		}
	}
}

// --- Helper ---

func strPtr(s string) *string {
	return &s
}
