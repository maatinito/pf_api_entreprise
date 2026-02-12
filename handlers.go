package main

import (
	"encoding/json"
	"log"
	"net/http"
)

// HandleEtablissements gère GET /etablissements/Entreprise?numeroTahiti=XXXXXX
func HandleEtablissements(store *DataStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusMethodNotAllowed)
			json.NewEncoder(w).Encode(map[string]string{"error": "method not allowed"})
			return
		}

		if !store.IsLoaded() {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]string{"error": "service not ready"})
			return
		}

		numeroTahiti := r.URL.Query().Get("numeroTahiti")
		if numeroTahiti == "" {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": "numeroTahiti parameter is required"})
			return
		}

		etabs := store.Lookup(numeroTahiti)

		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		if err := json.NewEncoder(w).Encode(etabs); err != nil {
			log.Printf("ERROR: impossible de sérialiser la réponse: %v", err)
		}
	}
}

// HandleHealthz gère GET /healthz
func HandleHealthz(store *DataStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		if store.IsLoaded() {
			w.WriteHeader(http.StatusOK)
			json.NewEncoder(w).Encode(map[string]interface{}{
				"status":  "ok",
				"entries": store.Count(),
			})
		} else {
			w.WriteHeader(http.StatusServiceUnavailable)
			json.NewEncoder(w).Encode(map[string]string{"status": "loading"})
		}
	}
}

// HandleReload gère POST /admin/reload
func HandleReload(store *DataStore, csvPath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusMethodNotAllowed)
			json.NewEncoder(w).Encode(map[string]string{"error": "method not allowed"})
			return
		}

		log.Println("Rechargement du CSV...")
		if err := store.Reload(csvPath); err != nil {
			log.Printf("ERROR: rechargement échoué: %v", err)
			w.Header().Set("Content-Type", "application/json; charset=utf-8")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
			return
		}

		log.Printf("CSV rechargé: %d établissements", store.Count())
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "reloaded",
			"entries": store.Count(),
		})
	}
}
