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

	// Charger le CSV
	log.Printf("Chargement du CSV: %s", csvPath)
	store, err := LoadCSV(csvPath)
	if err != nil {
		log.Fatalf("Impossible de charger le CSV: %v", err)
	}
	log.Printf("CSV chargé avec succès: %d établissements", store.Count())

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
