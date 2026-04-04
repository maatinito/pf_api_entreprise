package main

import (
	"log"
	"net/http"
	"os"
)

func main() {
	port := getEnv("PORT", "3000")
	csvPath := getEnv("CSV_PATH", "/data/exportrte.csv")
	logLevel := getEnv("LOG_LEVEL", "info")

	log.Printf("Démarrage pf-entreprise (port=%s, csv=%s, log=%s)", port, csvPath, logLevel)

	// Initialiser les tables de référence
	initReferences()

	// Créer le DataStore (vide, not ready)
	store := NewDataStore()

	// Tenter de charger le CSV — si absent, le serveur démarre en mode "not ready"
	log.Printf("Chargement du CSV: %s", csvPath)
	if err := store.Reload(csvPath); err != nil {
		log.Printf("WARNING: CSV non disponible au démarrage: %v", err)
		log.Printf("Le serveur démarre en mode 'not ready' — /healthz retournera 503")
		log.Printf("Utilisez POST /admin/reload une fois le CSV disponible")
	} else {
		log.Printf("CSV chargé avec succès: %d établissements", store.Count())
	}

	// Routes
	mux := http.NewServeMux()
	mux.HandleFunc("/etablissements/Entreprise", HandleEtablissements(store))
	mux.HandleFunc("/healthz", HandleHealthz(store))
	mux.HandleFunc("/admin/reload", HandleReload(store, csvPath))

	log.Printf("Serveur HTTP démarré sur le port %s", port)
	if err := http.ListenAndServe(":"+port, mux); err != nil {
		log.Fatalf("Erreur serveur: %v", err)
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
