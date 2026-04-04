package main

// Etablissement représente un établissement dans la réponse JSON.
// La structure reproduit exactement le contrat i-taiete.
type Etablissement struct {
	ID                  int           `json:"id"`
	Entreprise          *Entreprise   `json:"entreprise"`
	NumEtablissement    int           `json:"numEtablissement"`
	NomCommercial       *string       `json:"nomCommercial"`
	BoitePostale        *string       `json:"boitePostale"`
	AdressePostale      *string       `json:"adressePostale"`
	Telephone           *string       `json:"telephone"`
	Fax                 *string       `json:"fax"`
	PointKilometrique   *string       `json:"pointKilometrique"`
	Quartier            *string       `json:"quartier"`
	AdresseGeo          *string       `json:"adresseGeo"`
	CommuneGeo          *CommuneGeo   `json:"communeGeo"`
	Rue                 *string       `json:"rue"`
	Immeuble            *string       `json:"immeuble"`
	ActivitePrincipale  *ActiviteNAF  `json:"activitePrincipale"`
	ActiviteSecondaires []*ActiviteNAF `json:"activiteSecondaires"`
	DateInscription     *string       `json:"dateInscription"`
	DateModification    *string       `json:"dateModification"`
	DateReinscription   *string       `json:"dateReinscription"`
	DateRadiation       *string       `json:"dateRadiation"`
	Version             *string       `json:"version"`
}

// Entreprise représente l'objet entreprise imbriqué.
type Entreprise struct {
	ID                 int             `json:"id"`
	NumeroTahiti       string          `json:"numeroTahiti"`
	RaisonSociale      *string         `json:"raisonSociale"`
	Sigle              *string         `json:"sigle"`
	ClasseEffectif     *ClasseEffectif `json:"classeEffectif"`
	FormeJuridique     *FormeJuridique `json:"formeJuridique"`
	ActivitePrincipale *ActiviteNAF    `json:"activitePrincipale"`
	Commune            *CommuneGeo     `json:"commune"`
	Email              *string         `json:"email"`
	Telephone          *string         `json:"telephone"`
	AdressePostale     *string         `json:"adressePostale"`
	BoitePostale       *string         `json:"boitePostale"`
	DateInscription    *string         `json:"dateInscription"`
	DateModification   *string         `json:"dateModification"`
	DateRadiation      *string         `json:"dateRadiation"`
	DateReinscription  *string         `json:"dateReinscription"`
	Version            *string         `json:"version"`
}

// ClasseEffectif représente la classe d'effectif de l'entreprise.
type ClasseEffectif struct {
	ID      int    `json:"id"`
	Libelle string `json:"libelle"`
}

// FormeJuridique représente la forme juridique de l'entreprise.
type FormeJuridique struct {
	ID      int    `json:"id"`
	Code    string `json:"code"`
	Libelle string `json:"libelle"`
}

// CommuneGeo représente la commune géographique de l'établissement.
type CommuneGeo struct {
	ID              int          `json:"id"`
	CommuneAssociee string       `json:"communeAssociee"`
	CommuneMere     string       `json:"communeMere"`
	Subdivision     *Subdivision `json:"subdivision"`
	ChampImport     int          `json:"champImport"`
}

// Subdivision représente la subdivision administrative.
type Subdivision struct {
	ID      int    `json:"id"`
	Libelle string `json:"libelle"`
}

// ActiviteNAF représente une activité NAF.
type ActiviteNAF struct {
	ID      int    `json:"id"`
	Code    string `json:"code"`
	Libelle string `json:"libelle"`
}
