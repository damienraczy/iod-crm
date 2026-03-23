# Installation et Configuration : iod_job_intel (NC Market Intel)

Cette notice détaille la mise en place du module d'intelligence marché pour la Nouvelle-Calédonie intégré à Django-CRM.

## 1. Vue d'ensemble
`iod_job_intel` collecte les offres d'emploi de 4 sources calédoniennes (Gouv NC, Province Sud, Job.nc, L'Emploi.nc), les enrichit via un LLM (Ollama) et les lie au CRM via le numéro **RIDET (rid7)**.

---

## 2. Prérequis Systèmes & Dépendances

### A. Ollama
Doit être installé et tourner (en local ou via Docker).
- Modèle recommandé : `mistral` ou `llama3`.
- Commande : `ollama run mistral`

### B. Dépendances Python (Crucial)
Si vous rencontrez une erreur `ModuleNotFoundError: No module named 'bs4'`, installez les dépendances suivantes dans vos conteneurs :
```bash
docker exec -it iod-crm-backend-1 pip install beautifulsoup4 pyyaml
docker exec -it iod-crm-celery-worker-1 pip install beautifulsoup4 pyyaml
```

---

## 3. Configuration des Environnements (`.env.docker`)

Ajoutez ces variables pour configurer l'IA et les scrapers :

```env
# URL de l'instance Ollama (host.docker.internal pour pointer vers l'hôte depuis Docker)
OLLAMA_BASE_URL="http://host.docker.internal:11434"
OLLAMA_MODEL="mistral"

# Configuration des scrapers
SCRAPER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

---

## 4. Initialisation des Données (Ordre Critique)

### Étape 1 : Charger le référentiel RIDET
Le système utilise ce référentiel pour lier les offres aux entreprises du CRM. 
**Note :** L'API standard est limitée à 10 000 résultats. Le script utilise désormais l'API d'export pour charger l'intégralité des ~43 000 établissements.

```bash
# Import complet (peut prendre 1-2 minutes)
docker exec -it iod-crm-backend-1 python manage.py load_ridet --url

# Test rapide (20 premiers seulement)
docker exec -it iod-crm-backend-1 python manage.py load_ridet --url --limit 20
```

### Étape 2 : Charger les Prompts de l'IA
Importe les templates d'analyse et de rédaction d'e-mails pour Ollama.
```bash
docker exec -it iod-crm-backend-1 python manage.py load_prompts
```

### Étape 3 : Lancer une collecte manuelle
Pour collecter immédiatement toutes les offres de toutes les sources :
```bash
docker exec -it iod-crm-backend-1 python manage.py run_sync
```

---

## 5. Automatisation & Tâches de Fond

Le système utilise **Celery Beat** pour les tâches récurrentes.

| Tâche | Fréquence | Action |
| :--- | :--- | :--- |
| `collect_all_jobs` | Tous les jours (04:00) | Scrape les 4 sources NC |
| `analyze_new_jobs` | Toutes les heures | Analyse IA (scores, compétences) |

**Pour forcer une tâche Celery manuellement :**
```bash
docker exec -it iod-crm-backend-1 python manage.py shell -c "from iod_job_intel.tasks.cron_tasks import collect_all_jobs; collect_all_jobs.delay()"
```

---

## 6. Surveillance & Logs

- **Logs de collecte (Temps réel)** : 
  `docker logs -f iod-crm-celery-worker-1`
- **Historique en base** : 
  Consultez la table `ScrapeLog` dans l'interface d'administration Django (`/admin/iod_job_intel/scrapelog/`). Vous y verrez le nombre d'offres importées et les éventuelles erreurs par source.
- **Erreurs DNS (gaierror)** : 
  Si le conteneur ne résout pas les sites (ex: job.nc), vérifiez la configuration DNS de Docker ou utilisez le nom technique du serveur.
