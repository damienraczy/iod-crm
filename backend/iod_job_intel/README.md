# iod_job_intel — Intelligence Marché de l'Emploi NC

Application Django 5.2 intégrée à django-crm. Elle collecte et centralise les offres d'emploi
publiées en Nouvelle-Calédonie depuis quatre sources, les enrichit via un LLM local (Ollama),
et expose les données via une API REST protégée par JWT.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Modèles de données](#3-modèles-de-données)
4. [Services](#4-services)
5. [Scrapers](#5-scrapers)
6. [API REST](#6-api-rest)
7. [Commandes de gestion](#7-commandes-de-gestion)
8. [Templates de prompts](#8-templates-de-prompts)
9. [Installation dans django-crm](#9-installation-dans-django-crm)
10. [Configuration](#10-configuration)
11. [Tests](#11-tests)
12. [Signaux](#12-signaux)
13. [Référence rapide](#13-référence-rapide)

---

## 1. Vue d'ensemble

### Contexte métier

L'application sert à identifier des opportunités de prospection commerciale à partir du marché
de l'emploi calédonien. Une entreprise qui recrute est une entreprise en mouvement — c'est un signal
d'entrée en relation pour un cabinet de conseil en ressources humaines.

Le flux complet est le suivant :

```
Sources externes → Scrapers → JobOffer (DB) → AnalysisService (score) → AIService (LLM)
                                    ↓
                               Liaison rid7 → django-crm (Account / Contact)
```

### Principe de couplage faible avec django-crm

`iod_job_intel` ne connaît **pas** les modèles de django-crm. La liaison se fait uniquement via
le **rid7** : identifiant à 7 chiffres du registre officiel RIDET (Registre Identifiant Des
ETablissements) de la Nouvelle-Calédonie. C'est une clé naturelle — pas de `ForeignKey`.

```
django-crm                     iod_job_intel
──────────                     ─────────────
Account.ridet  ←── rid7 ───→  JobOffer.rid7
                               AIAnalysis.rid7
```

### Sources de données

| Identifiant  | Site                    | Méthode               |
|:-------------|:------------------------|:----------------------|
| `GOUV_NC`    | data.gouv.nc            | API OpenDataSoft v2.1 |
| `PSUD`       | emploi.province-sud.nc  | HTML + API Boost JSON |
| `JOB_NC`     | job.nc                  | HTML Drupal CMS       |
| `LEMPLOI_NC` | lemploi.nc              | JSON-LD + HTML        |

---

## 2. Architecture

```
iod_job_intel/
├── apps.py                  # AppConfig, charge les signaux au démarrage
├── models.py                # 6 modèles Django ORM
├── admin.py                 # Interface d'administration
├── signals.py               # Signal job_offer_created
│
├── services/
│   ├── ai_service.py        # Appels LLM via Ollama
│   ├── ridet_service.py     # Index mémoire du référentiel RIDET
│   └── analysis_service.py  # Score de priorité, intensité de recrutement
│
├── scrapers/
│   ├── base.py              # BaseScraper (déduplication, réconciliation)
│   ├── gouv_nc.py           # OpenDataSoft API
│   ├── province_sud.py      # Province Sud (2 passes)
│   ├── job_nc.py            # Job.nc Drupal (2 passes)
│   └── lemploi_nc.py        # L'Emploi.nc JSON-LD (2 passes)
│
├── api/
│   ├── serializers.py       # Sérialiseurs DRF
│   ├── views.py             # ViewSets + vues spéciales
│   └── urls.py              # Routes REST
│
├── management/commands/
│   ├── run_sync.py          # Lance un ou plusieurs scrapers
│   ├── load_ridet.py        # Charge le référentiel RIDET
│   └── load_prompts.py      # Charge les prompts .txt en base
│
├── prompts/                 # Templates de prompts Ollama (fichiers fallback)
│   ├── skill_analysis.txt
│   ├── offer_diagnostic.txt
│   ├── questions_brulantes.txt
│   ├── questions_brulantes_offre.txt
│   ├── email_prospect_job.txt
│   ├── email_prospect_general.txt
│   ├── ice_breaker.txt
│   ├── system_R6_I6_skills.txt
│   └── system_R6_O6_capacities.txt
│
├── migrations/              # Migrations Django
└── tests/
    ├── test_models.py
    ├── test_services.py
    └── test_api.py
```

### Flux de données d'un scraping

```
run_sync command
      │
      ▼
BaseScraper.__init__()
  ├── ScrapeLog.objects.create()   # journal ouvert
  ├── RidetService()               # index mémoire chargé
  └── AnalysisService()            # calculateur de score

BaseScraper.run()
  ├── collecter les offres de la source
  ├── pour chaque offre :
  │     ├── _reconcile_company()   # nom → rid7 via RidetService
  │     ├── calculate_score()      # score 0-100 (transient JobOffer)
  │     └── _save_offer()          # get_or_create (external_id, source)
  └── _finalize_log()              # ScrapeLog.finalize()
```

---

## 3. Modèles de données

### JobOffer

Offre d'emploi importée depuis une source externe.

| Champ            | Type                        | Description                                          |
|:-----------------|-----------------------------|:-----------------------------------------------------|
| `external_id`    | CharField(100)              | Identifiant de la source (ex. `JOB_NC-12345`)        |
| `source`         | TextChoices                 | `GOUV_NC`, `PSUD`, `JOB_NC`, `LEMPLOI_NC`           |
| `title`          | CharField(255)              | Intitulé du poste                                    |
| `description`    | TextField                   | Description complète (HTML nettoyé)                  |
| `raw_description`| TextField                   | HTML brut de la source                               |
| `rome_code`      | CharField(10)               | Code ROME si fourni                                  |
| `contract_type`  | CharField(50)               | CDI, CDD, etc.                                       |
| `location`       | CharField(100)              | Localisation géographique                            |
| `experience_req` | CharField(100)              | Expérience requise (texte libre)                     |
| `education_req`  | TextField                   | Formation requise                                    |
| `nb_postes`      | PositiveSmallIntegerField   | Nombre de postes ouverts                             |
| `url_external`   | URLField(500)               | URL de l'offre sur la source                         |
| `skills_json`    | JSONField                   | Liste de compétences structurées                     |
| `activities_json`| JSONField                   | Liste d'activités structurées                        |
| `date_published` | DateTimeField               | Date de publication                                  |
| `status`         | TextChoices                 | `NEW`, `PUBLIEE`, `ARCHIVEE`                         |
| `score`          | PositiveSmallIntegerField   | Score de priorité 0–100                              |
| `rid7`           | CharField(20)               | Pivot vers django-crm (pas de FK)                    |
| `company_name`   | CharField(255)              | Nom de l'entreprise tel que publié                   |

**Contrainte d'unicité :** `unique_together = [("external_id", "source")]` — le même
`external_id` peut exister sur deux sources différentes.

**Score de priorité** (calculé par `AnalysisService.calculate_score()`) :

| Critère                      | Points |
|:-----------------------------|-------:|
| Contrat CDI                  | +20    |
| Expérience ≥ 5 ans           | +30    |
| Expérience 1–4 ans           | +15    |
| Formation Bac+5 / Master     | +20    |
| Formation Bac+3 / Licence    | +10    |
| Multi-postes (nb_postes ≥ 2) | +10    |
| **Plafond**                  | **100**|

---

### RidetEntry

Entrée du registre officiel RIDET des établissements actifs en Nouvelle-Calédonie.

| Champ              | Type           | Description                              |
|:-------------------|----------------|:-----------------------------------------|
| `rid7`             | CharField(20)  | Numéro RIDET à 7 chiffres (unique)       |
| `denomination`     | CharField(255) | Raison sociale officielle                |
| `sigle`            | CharField(100) | Sigle ou abréviation                     |
| `enseigne`         | CharField(255) | Nom commercial (enseigne)                |
| `date_etablissement`| DateField     | Date de création de l'établissement      |
| `commune`          | CharField(100) | Commune                                  |
| `province`         | CharField(100) | Province (Sud, Nord, Îles)               |
| `forme_juridique`  | CharField(100) | SA, SARL, SAS, EURL, etc.               |

---

### AIAnalysis

Résultat d'une analyse LLM Ollama. Peut être lié à une offre ou à un rid7.

| Champ           | Type           | Description                                         |
|:----------------|----------------|:----------------------------------------------------|
| `job_offer`     | FK → JobOffer  | Nullable — analyse liée à une offre                 |
| `rid7`          | CharField(20)  | Nullable — analyse liée à une entreprise            |
| `analysis_type` | TextChoices    | Type d'analyse (voir ci-dessous)                    |
| `model_used`    | CharField(100) | Modèle Ollama utilisé (ex. `qwen3:latest`)          |
| `prompt_hash`   | CharField(64)  | SHA-256 du prompt (cache / déduplication)           |
| `result_text`   | TextField      | Réponse brute du LLM                                |
| `result_json`   | JSONField      | Réponse parsée si JSON valide                       |
| `language`      | CharField(20)  | Langue utilisée pour le prompt                      |

**Types d'analyse (`AIAnalysisType`) :**

| Valeur                 | Description                                         |
|:-----------------------|:----------------------------------------------------|
| `skill_analysis`       | 3 compétences critiques (JSON)                      |
| `offer_diagnostic`     | Diagnostic qualitatif de l'offre                    |
| `questions_offre`      | 7 questions brûlantes sur les compétences requises  |
| `questions_company`    | 7 questions brûlantes sur la capacité organisationnelle |
| `email_job`            | Email de prospection lié à une offre spécifique     |
| `email_general`        | Email de prospection général entreprise             |
| `ice_breaker`          | Phrase d'accroche personnalisée                     |

---

### PromptTemplate

Templates de prompts Ollama stockés en base et modifiables via l'admin Django.

| Champ        | Type          | Description                                       |
|:-------------|---------------|:--------------------------------------------------|
| `name`       | SlugField     | Identifiant unique (ex. `skill_analysis`)         |
| `template`   | TextField     | Corps du prompt avec variables `{variable}`       |
| `is_system`  | BooleanField  | `True` = system prompt Ollama                     |
| `version`    | SmallIntegerField | Numéro de version                             |

---

### ScrapeLog

Journal d'une session de scraping.

| Champ             | Type          | Description                                       |
|:------------------|---------------|:--------------------------------------------------|
| `source`          | TextChoices   | Source scrapée                                    |
| `started_at`      | DateTimeField | Horodatage de début                               |
| `finished_at`     | DateTimeField | Horodatage de fin                                 |
| `status`          | TextChoices   | `RUNNING`, `SUCCESS`, `PARTIAL`, `FAILED`         |
| `offers_imported` | IntegerField  | Offres créées                                     |
| `offers_skipped`  | IntegerField  | Offres ignorées (déjà connues)                    |
| `error_message`   | TextField     | Message d'erreur si `FAILED`                      |

Méthode `finalize(imported, skipped, error="")` — à appeler en fin de scraping.

---

### AppParameter

Configuration dynamique clé/valeur (remplace un fichier `config.yaml`).

```python
# Lecture
AppParameter.get("ai.default_model")              # → str | None
AppParameter.get("ai.default_model", "llama3.2")  # → str avec défaut
AppParameter.get_int("scraper.gouv_nc.limit", 50) # → int
AppParameter.get_float("scraper.delay", 1.0)      # → float
```

**Paramètres reconnus :**

| Clé                            | Défaut        | Description                           |
|:-------------------------------|:--------------|:--------------------------------------|
| `ai.default_model`             | (settings)    | Modèle Ollama par défaut              |
| `ai.timeout`                   | `60`          | Timeout HTTP vers Ollama (secondes)   |
| `scraper.gouv_nc.limit`        | `50`          | Nombre max d'offres GOUV_NC           |
| `scraper.jobnc.anteriorite_jours` | `30`       | Fenêtre temporelle Job.nc (jours)     |
| `scraper.request_delay`        | `1.0`         | Délai entre requêtes scraper (s)      |

---

## 4. Services

### AIService (`services/ai_service.py`)

Wrapper autour de l'API REST Ollama (`POST /api/generate`).

```python
from iod_job_intel.services.ai_service import AIService

svc = AIService()  # modèle lu depuis AppParameter ou settings.OLLAMA_DEFAULT_MODEL

# Analyse des compétences critiques (retourne dict avec clé "critical_skills")
result = svc.analyze_offer(title, experience, skills, language)

# Diagnostic de l'offre (retourne str)
diagnostic = svc.diagnose_offer(title, description, contract_type, language)

# Questions brûlantes sur l'offre (retourne str)
questions = svc.generate_questions_brulantes_offre(title, experience, education, language)

# Questions brûlantes sur la capacité organisationnelle (retourne str)
questions = svc.generate_questions_brulantes(company_name, activity, language)

# Email de prospection lié à une offre (retourne str)
email = svc.generate_email(title, source, contact_name, questions_brulantes, language)

# Email de prospection général (retourne str)
email = svc.generate_email_general(company_name, activity, contact_name, language)

# Phrase d'accroche (retourne str)
ice = svc.generate_ice_breaker(company_name, activity, language)
```

**Résolution des prompts** (par ordre de priorité) :

1. `PromptTemplate.objects.get(name=<slug>)` — base de données (modifiable via admin)
2. `iod_job_intel/prompts/<slug>.txt` — fichier de fallback

**Mécanisme de retry** : `_post_with_retry(payload, max_retries=3)` — relance automatiquement
en cas de `ConnectionError` avec backoff linéaire (délai × numéro de tentative).

---

### RidetService (`services/ridet_service.py`)

Index mémoire du référentiel RIDET. Utilisé par les scrapers pour résoudre un nom
d'entreprise en rid7.

```python
from iod_job_intel.services.ridet_service import RidetService

svc = RidetService()

rid7 = svc.get_rid7_by_name("AIR CALEDONIE")       # → "1234567" ou None
rid7 = svc.get_rid7_by_name("air calédonie")        # insensible à la casse
name = svc.get_official_name("1234567")             # → "AIR CALEDONIE" ou "Entreprise Inconnue"

# Invalider le cache (après load_ridet)
RidetService.invalidate_cache()
```

**Fonctionnement** :
- L'index est chargé **une seule fois** (variable de classe `_loaded`), depuis `RidetEntry.objects.all()`.
- Si la table est vide, tente un CSV de fallback (`data/ridet.csv`).
- Les noms génériques (`SARL`, `SAS`, `SA`, `NC`, `Anonyme`) sont ignorés.
- La résolution cherche dans `denomination` et `enseigne`.

---

### AnalysisService (`services/analysis_service.py`)

```python
from iod_job_intel.services.analysis_service import AnalysisService

svc = AnalysisService()

# Score de priorité 0-100 (ne sauvegarde pas — travaille sur une instance transiente)
score = svc.calculate_score(job_offer_instance)

# Détecte si l'offre ressemble à d'autres offres récentes du même employeur
result = svc.detect_recurrence(job_offer_instance)
# → {"is_recurrent": bool, "similar_count": int, "similar_titles": [...]}

# Intensité de recrutement d'une entreprise
result = svc.get_company_recruitment_intensity(rid7)
# → {"total_offers": int, "distinct_roles": int, "is_growing": bool, "sources": [...]}
```

---

## 5. Scrapers

### BaseScraper (`scrapers/base.py`)

Classe abstraite dont héritent tous les scrapers.

```python
class MonScraper(BaseScraper):
    source_id = "MON_SOURCE"   # correspond à Source.choices
    request_delay = 1.5        # secondes entre requêtes

    def run(self, **kwargs) -> dict:
        # collecter + _save_offer() pour chaque offre
        # retourner {"imported": n, "skipped": m}
        ...
```

**Méthodes utilitaires disponibles :**

| Méthode                    | Description                                               |
|:---------------------------|:----------------------------------------------------------|
| `_reconcile_company(name)` | Retourne `(rid7, company_name)` via RidetService          |
| `_save_offer(data: dict)`  | `get_or_create` sur `(external_id, source)`, calcule score|
| `_sleep()`                 | Attend `request_delay` secondes                           |
| `_finalize_log(n, m, err)` | Clôture le ScrapeLog                                      |

---

### GouvNCScraper (`scrapers/gouv_nc.py`)

Source : API OpenDataSoft v2.1 — dataset `historique_emploi_gouv_nc` sur data.gouv.nc.

- Authentification : aucune (API publique)
- Paramètre `limit` : nombre d'offres à récupérer (défaut : `AppParameter.get_int("scraper.gouv_nc.limit", 50)`)
- Format `external_id` : champ `identifiant` de l'API

```bash
python manage.py run_sync --sources GOUV_NC --limit 100
```

---

### ProvinceSudScraper (`scrapers/province_sud.py`)

Source : [emploi.province-sud.nc](https://emploi.province-sud.nc)

**Passe 1** — collecte des identifiants depuis la page de liste HTML :
- Regex sur les liens `/offres/OF-YYYY-MM-NNN`

**Passe 2** — détail via l'API Boost JSON :
- URL : `/api/offres/{id}`
- Extraction enseigne / raison sociale depuis le format `NOM ENSEIGNE (RAISON SOCIALE)`

Format `external_id` : `OF-YYYY-MM-NNN` (ex. `OF-2024-11-042`)

---

### JobNCScraper (`scrapers/job_nc.py`)

Source : [job.nc](https://www.job.nc) (Drupal CMS)

**Passe 1** — liste paginée des offres récentes :
- Filtre par date de publication (`days` jours en arrière, défaut 30)
- Collecte les slugs (`/offres-emploi/{slug}`)

**Passe 2** — page de détail :
- Parse HTML BeautifulSoup
- Extrait le `node_id` depuis les classes CSS `<body class="node-12345 ...">` pour un `external_id` stable

Format `external_id` : `JOB_NC-{node_id}` (ex. `JOB_NC-98765`)

---

### LemploiNCScraper (`scrapers/lemploi_nc.py`)

Source : [lemploi.nc](https://www.lemploi.nc) (Laravel + Inertia.js)

**Passe 1** — liste paginée :
- Collecte les slugs depuis les balises `<a href="/offres/{slug}">`

**Passe 2** — détail :
- Source principale : bloc `<script type="application/ld+json">` (JSON-LD `JobPosting`)
- Complément : sidebar HTML pour le nom de l'entreprise et la localisation

Format `external_id` : `LEMPLOI_NC-{id}` où `{id}` est le dernier segment numérique du slug

---

## 6. API REST

Base URL : `/api/iod/`
Authentification : JWT Bearer Token (compatible django-crm)

### Offres d'emploi

```
GET  /api/iod/offers/                   Liste paginée
GET  /api/iod/offers/{id}/              Détail (avec description)
GET  /api/iod/offers/{id}/analyses/     Analyses IA liées
```

**Filtres disponibles :**

| Paramètre  | Exemple               | Description                          |
|:-----------|:----------------------|:-------------------------------------|
| `rid7`     | `?rid7=1234567`       | Offres d'une entreprise              |
| `source`   | `?source=JOB_NC`      | Par source                           |
| `status`   | `?status=PUBLIEE`     | Par statut                           |
| `q`        | `?q=développeur`      | Recherche fulltext titre + entreprise|

**Format de réponse liste :**
```json
{
  "count": 42,
  "next": "/api/iod/offers/?offset=10",
  "previous": null,
  "results": [
    {
      "id": 1,
      "external_id": "JOB_NC-98765",
      "source": "JOB_NC",
      "title": "Développeur Python",
      "company_name": "TechNC",
      "rid7": "1234567",
      "contract_type": "CDI",
      "score": 50,
      "status": "NEW",
      "date_published": "2024-11-15T08:00:00Z",
      "url_external": "https://www.job.nc/offres-emploi/..."
    }
  ]
}
```

La vue détail ajoute les champs `description`, `experience_req`, `education_req`,
`skills_json`, `activities_json`.

---

### Recherche RIDET

```
GET /api/iod/ridet/search/?q=air
```

- Paramètre `q` obligatoire, minimum 2 caractères
- Recherche dans `denomination`, `enseigne`, `sigle`
- Retourne jusqu'à 20 résultats (tableau JSON, pas de pagination)

```json
[
  {"rid7": "1234567", "denomination": "AIR CALEDONIE", "enseigne": "", "commune": "Nouméa"}
]
```

---

### Journaux de scraping

```
GET /api/iod/logs/              50 derniers journaux
GET /api/iod/logs/?source=PSUD  Filtré par source
```

```json
{
  "count": 12,
  "results": [
    {
      "id": 5,
      "source": "GOUV_NC",
      "started_at": "2024-11-15T06:00:00Z",
      "finished_at": "2024-11-15T06:00:45Z",
      "status": "SUCCESS",
      "offers_imported": 23,
      "offers_skipped": 17,
      "duration_seconds": 45,
      "error_message": ""
    }
  ]
}
```

---

### Paramètres de configuration

```
GET   /api/iod/parameters/                     Liste
GET   /api/iod/parameters/{key}/               Détail
PATCH /api/iod/parameters/{key}/               Mise à jour valeur
```

Les clés peuvent contenir des points (`ai.default_model`, `scraper.limit`).

```bash
# Exemple : changer le modèle Ollama par défaut
curl -X PATCH /api/iod/parameters/ai.default_model/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"value": "qwen3:latest"}'
```

---

### Déclenchement manuel de synchronisation

```
POST /api/iod/sync/trigger/
```

```json
{
  "sources": ["GOUV_NC", "PSUD"],
  "limit": 20,
  "days": 7
}
```

Exécution **synchrone** (bloquante). À terme, sera remplacée par une tâche Celery.

---

### Analyses IA

```
GET /api/iod/analyses/              Liste
GET /api/iod/analyses/{id}/         Détail
GET /api/iod/analyses/?rid7=1234567 Par entreprise
GET /api/iod/analyses/?type=email_job Par type
```

---

## 7. Commandes de gestion

### `run_sync` — Lancer les scrapers

```bash
# Toutes les sources
python manage.py run_sync

# Sources spécifiques
python manage.py run_sync --sources GOUV_NC PSUD

# Avec limite et fenêtre temporelle
python manage.py run_sync --sources GOUV_NC --limit 50
python manage.py run_sync --sources JOB_NC --days 14
```

**Options :**

| Option       | Défaut          | Description                              |
|:-------------|:----------------|:-----------------------------------------|
| `--sources`  | toutes          | Noms des sources à activer               |
| `--limit`    | (AppParameter)  | Nombre max d'offres pour GOUV_NC         |
| `--days`     | (AppParameter)  | Fenêtre temporelle pour JOB_NC           |

---

### `load_ridet` — Charger le référentiel RIDET

```bash
# Depuis un fichier CSV
python manage.py load_ridet --csv /path/to/ridet.csv

# Depuis l'API data.gouv.nc (téléchargement automatique)
python manage.py load_ridet --url

# Vider et recharger complètement
python manage.py load_ridet --csv /path/to/ridet.csv --clear
```

**Format CSV attendu :**
Colonnes : `rid7`, `denomination`, `sigle`, `enseigne`, `date_etablissement`, `commune`, `province`, `forme_juridique`

Après chargement, le cache de `RidetService` est invalidé automatiquement.

---

### `load_prompts` — Charger les prompts en base

```bash
# Depuis le répertoire par défaut (iod_job_intel/prompts/)
python manage.py load_prompts

# Depuis un répertoire personnalisé
python manage.py load_prompts --dir /path/to/prompts/

# Écraser les prompts existants
python manage.py load_prompts --overwrite
```

Convention de nommage :
- `system_*.txt` → `is_system = True`
- `*.txt` → `is_system = False`
- Le nom du template = nom du fichier sans extension (ex. `skill_analysis.txt` → slug `skill_analysis`)

---

## 8. Templates de prompts

Les prompts sont stockés dans `iod_job_intel/prompts/` et chargés en base via `load_prompts`.
Une fois en base, ils sont modifiables depuis l'interface d'administration Django sans redéploiement.

| Fichier                        | Usage                                       | Variables                                              |
|:-------------------------------|:--------------------------------------------|:-------------------------------------------------------|
| `skill_analysis.txt`           | Analyse des 3 compétences critiques         | `{title}`, `{experience}`, `{skills}`, `{language}`   |
| `offer_diagnostic.txt`         | Diagnostic qualitatif de l'offre            | `{title}`, `{description}`, `{contract}`, `{language}`|
| `questions_brulantes_offre.txt`| 7 questions sur les compétences requises    | `{title}`, `{experience}`, `{education}`, `{language}`|
| `questions_brulantes.txt`      | 7 questions sur la capacité organisationnelle| `{company}`, `{activity}`, `{language}`              |
| `email_prospect_job.txt`       | Email de prospection (offre spécifique)     | `{title}`, `{source}`, `{contact_name}`, `{questions_brulantes}`, `{language}` |
| `email_prospect_general.txt`   | Email de prospection (entreprise)           | `{company}`, `{activity}`, `{contact_name}`, `{language}` |
| `ice_breaker.txt`              | Phrase d'accroche email                     | `{company}`, `{activity}`, `{language}`               |
| `system_R6_I6_skills.txt`      | System prompt — 6 compétences individuelles | *(system prompt, pas de variables)*                   |
| `system_R6_O6_capacities.txt`  | System prompt — 6 capacités organisationnelles | *(system prompt, pas de variables)*              |

---

## 9. Installation dans django-crm

### Prérequis

```
Python 3.12+
beautifulsoup4==4.12.3  (déjà dans requirements.txt)
pyyaml==6.0.2           (déjà dans requirements.txt)
requests                (déjà dans requirements.txt via djangorestframework)
Ollama                  (serveur local, https://ollama.com)
```

### Étape 1 — INSTALLED_APPS

Dans `crm/settings.py` :

```python
INSTALLED_APPS = [
    # ... apps existantes ...
    "iod_job_intel",
]
```

### Étape 2 — URLs

Dans `crm/urls.py` :

```python
from django.urls import include, path

urlpatterns = [
    # ... patterns existants ...
    path("api/iod/", include("iod_job_intel.api.urls")),
]
```

### Étape 3 — Variables d'environnement

Dans `.env` (ou `.env.docker`) :

```dotenv
OLLAMA_CLOUD_URL
OLLAMA_DEFAULT_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=60
```

Dans `crm/settings.py` (déjà ajouté) :

```python
OLLAMA_CLOUD_URL      = os.environ.get("OLLAMA_CLOUD_URL", "")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:latest")
OLLAMA_TIMEOUT       = int(os.environ.get("OLLAMA_TIMEOUT", "60"))
```

### Étape 4 — Migrations

```bash
python manage.py makemigrations iod_job_intel
python manage.py migrate
```

Ou depuis Docker :

```bash
docker exec django-crm-backend-1 python manage.py makemigrations iod_job_intel
docker exec django-crm-backend-1 python manage.py migrate
```

### Étape 5 — Données initiales

```bash
# Charger les prompts depuis les fichiers .txt
python manage.py load_prompts

# Charger le référentiel RIDET (choisir une méthode)
python manage.py load_ridet --url           # depuis data.gouv.nc
python manage.py load_ridet --csv ridet.csv # depuis fichier local
```

### Étape 6 — Premier test de scraping

```bash
# Tester avec 10 offres GOUV_NC (source la plus fiable)
python manage.py run_sync --sources GOUV_NC --limit 10
```

Vérifier dans l'admin Django (`/admin/iod_job_intel/`) que les offres apparaissent.

---

## 10. Configuration

### Variables prioritaires

La résolution d'un paramètre suit cet ordre :

1. `AppParameter` (base de données) — modifiable à chaud via admin ou API
2. `django.conf.settings` (settings.py + variables d'environnement)
3. Valeur par défaut codée dans le service

### Gestion via l'admin Django

L'interface d'administration (`/admin/iod_job_intel/appparameter/`) permet de modifier
les paramètres sans redémarrage.

### Gestion via l'API

```bash
# Voir tous les paramètres
curl /api/iod/parameters/ -H "Authorization: Bearer <token>"

# Modifier le modèle Ollama
curl -X PATCH /api/iod/parameters/ai.default_model/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"value": "qwen3:latest"}'
```

---

## 11. Tests

### Lancer les tests

```bash
# Dans le container Docker
docker exec django-crm-backend-1 python -m pytest iod_job_intel/tests/ -v --no-cov

# En local (si Django installé)
cd backend/
DJANGO_SETTINGS_MODULE=crm.test_settings python -m pytest iod_job_intel/tests/ -v
```

### Structure des tests

```
tests/
├── test_models.py    # 5 classes, ~25 tests — création, contraintes, méthodes de classe
├── test_services.py  # AnalysisService (score), RidetService (cache), AIService (mock Ollama)
└── test_api.py       # API REST complète — auth, filtres, pagination, détail, actions
```

### Ce qui est testé

**`test_models.py`** :
- `TestJobOffer` — création minimale, déduplication `(external_id, source)`, champ `skills_json`, `__str__`
- `TestRidetEntry` — création, contrainte `unique rid7`
- `TestAppParameter` — `get()`, `get_int()`, valeurs manquantes
- `TestScrapeLog` — `finalize()` succès et erreur
- `TestAIAnalysis` — liaison à une offre ou à un rid7
- `TestPromptTemplate` — system prompts

**`test_services.py`** :
- `TestAnalysisService` — calcul du score pour chaque critère et combinaisons, intensité de recrutement
- `TestRidetService` — résolution par denomination et enseigne, casse, noms génériques ignorés, invalidation du cache
- `TestAIServicePrompts` — `analyze_offer`, `generate_email`, retry réseau (mock `requests.post`)

**`test_api.py`** :
- `TestJobOfferAPI` — liste, détail, filtres `rid7`/`source`/`q`, séparateur list/detail (champ `description`), sous-ressource `/analyses/`
- `TestRidetSearchAPI` — auth, validation `q`, résultats
- `TestScrapeLogAPI` — liste, filtre source
- `TestAppParameterAPI` — liste, récupération par clé dotted, mise à jour PATCH

### Configuration pytest

Les tests utilisent `crm.test_settings` (SQLite en mémoire, pas de PostgreSQL, pas de Redis).
La fixture `admin_client` (définie dans `conftest.py` du projet) fournit un `APIClient` DRF
avec un token JWT valide incluant le contexte d'organisation.

---

## 12. Signaux

### `job_offer_created`

Signal personnalisé émis après la création d'une nouvelle offre **avec un rid7 connu**.

```python
from iod_job_intel.signals import job_offer_created

# S'abonner depuis une autre app (ex. dans accounts/apps.py)
@receiver(job_offer_created)
def on_new_offer(sender, job_offer_id, rid7, title, company_name, score, **kwargs):
    # Exemple : créer une activité dans le CRM pour l'Account correspondant
    account = Account.objects.filter(ridet=rid7).first()
    if account:
        Activity.objects.create(
            account=account,
            note=f"Nouvelle offre détectée : {title} (score {score})",
        )
```

**Payload du signal :**

| Argument       | Type  | Description                        |
|:---------------|:------|:-----------------------------------|
| `job_offer_id` | int   | PK de l'offre créée                |
| `rid7`         | str   | RIDET de l'entreprise              |
| `title`        | str   | Intitulé du poste                  |
| `company_name` | str   | Nom de l'entreprise                |
| `score`        | int   | Score de priorité calculé          |
| `source`       | str   | Source de l'offre                  |

---

## 13. Référence rapide

### Commandes Docker courantes

```bash
# Migrations
docker exec django-crm-backend-1 python manage.py makemigrations iod_job_intel
docker exec django-crm-backend-1 python manage.py migrate

# Données initiales
docker exec django-crm-backend-1 python manage.py load_prompts
docker exec django-crm-backend-1 python manage.py load_ridet --url

# Scraping
docker exec django-crm-backend-1 python manage.py run_sync --sources GOUV_NC --limit 10
docker exec django-crm-backend-1 python manage.py run_sync

# Tests
docker exec django-crm-backend-1 python -m pytest iod_job_intel/tests/ -v --no-cov
```

### Endpoints API résumés

| Méthode | URL                             | Description                        |
|:--------|:--------------------------------|:-----------------------------------|
| GET     | `/api/iod/offers/`              | Liste des offres (paginée)         |
| GET     | `/api/iod/offers/{id}/`         | Détail d'une offre                 |
| GET     | `/api/iod/offers/{id}/analyses/`| Analyses IA de l'offre             |
| GET     | `/api/iod/analyses/`            | Liste des analyses IA              |
| GET     | `/api/iod/ridet/search/?q=...`  | Recherche établissement RIDET      |
| GET     | `/api/iod/logs/`                | Journaux de scraping               |
| GET     | `/api/iod/parameters/`          | Paramètres de configuration        |
| PATCH   | `/api/iod/parameters/{key}/`    | Modifier un paramètre              |
| POST    | `/api/iod/sync/trigger/`        | Déclencher un scraping             |

### Modèles résumés

| Modèle          | Rôle                                  | Clé naturelle            |
|:----------------|:--------------------------------------|:-------------------------|
| `JobOffer`      | Offre d'emploi                        | `(external_id, source)`  |
| `RidetEntry`    | Établissement NC (registre RIDET)     | `rid7`                   |
| `AIAnalysis`    | Résultat d'analyse LLM                | `(job_offer, type)` ou `(rid7, type)` |
| `PromptTemplate`| Template de prompt Ollama             | `name` (slug)            |
| `ScrapeLog`     | Journal de scraping                   | `(source, started_at)`   |
| `AppParameter`  | Configuration clé/valeur              | `key`                    |
