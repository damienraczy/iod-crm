# iod_job_intel — Intelligence Marché de l'Emploi NC

Application Django 5.2 intégrée à django-crm. Elle collecte et centralise les offres d'emploi
publiées en Nouvelle-Calédonie depuis quatre sources, les enrichit via un LLM (Ollama cloud),
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
                               RidetEntry.rid7
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
├── models.py                # 7 modèles Django ORM
├── admin.py                 # Interface d'administration
├── signals.py               # Signal job_offer_created
│
├── services/
│   ├── ai_service.py        # Appels LLM via Ollama cloud
│   ├── ridet_service.py     # Index mémoire du référentiel RIDET
│   └── analysis_service.py  # Score de priorité, intensité de recrutement
│
├── scrapers/
│   ├── base.py              # BaseScraper (déduplication, réconciliation)
│   ├── gouv_nc.py           # OpenDataSoft API
│   ├── province_sud.py      # Province Sud (2 passes)
│   ├── job_nc.py            # Job.nc Drupal (2 passes)
│   ├── lemploi_nc.py        # L'Emploi.nc JSON-LD (2 passes)
│   ├── infogreffe_nc.py     # Infogreffe.nc — dirigeants et données légales
│   └── avisridet_nc.py      # avisridet.isee.nc — PDF Avis de situation RIDET
│
├── api/
│   ├── serializers.py       # Sérialiseurs DRF
│   ├── views.py             # ViewSets + vues spéciales
│   └── urls.py              # Routes REST
│
├── management/commands/
│   ├── run_sync.py          # Lance un ou plusieurs scrapers
│   ├── load_ridet.py        # Charge le référentiel RIDET
│   ├── load_prompts.py      # Charge les prompts .txt en base
│   └── seed_eval_products.py# Crée les produits évaluation eval_n4…eval_n8
│
├── prompts/                 # Templates de prompts Ollama (fichiers fallback)
│   ├── skill_analysis.txt
│   ├── offer_diagnostic.txt
│   ├── classify_offer.txt
│   ├── extract_ridet_pdf.txt
│   ├── questions_brulantes_company.txt
│   ├── questions_brulantes_offre.txt
│   ├── email_prospect_job.txt
│   ├── email_prospect_general.txt
│   ├── ice_breaker.txt
│   ├── system_R6_I6_skills.txt
│   └── system_R6_O6_capacities.txt
│
├── migrations/              # Migrations Django (dont migrations de données)
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

### Flux de consolidation RIDET

```
Frontend (bouton "Consolider RIDET")
  │
  ├── POST /api/iod/ridet/<rid7>/consolidate/
  │     → InfogreffeScraper.fetch(rid7)
  │       → dirigeants, adresse, code_naf, activite_principale
  │
  └── POST /api/iod/ridet/<rid7>/extract-ridet/
        → AvisRidetScraper(rid7).run()
          → Playwright + Browserless → avisridet.isee.nc
          → PDF téléchargé → pdfplumber → texte extrait
          → AIService.extract_ridet_pdf(text)
            → LLM (classifier, temperature=0.0) → JSON structuré
          → RidetEntry.save() (update_fields sans description)
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
| `qualification`  | CharField(100)              | Qualification requise                                |
| `nb_postes`      | PositiveSmallIntegerField   | Nombre de postes ouverts                             |
| `url_external`   | URLField(500)               | URL de l'offre sur la source                         |
| `skills_json`    | JSONField                   | Liste de compétences structurées                     |
| `activities_json`| JSONField                   | Liste d'activités structurées                        |
| `date_published` | DateTimeField               | Date de publication                                  |
| `status`         | TextChoices                 | `NEW`, `PUBLIEE`, `ARCHIVEE`                         |
| `score`          | PositiveSmallIntegerField   | Score de priorité 0–100                              |
| `eval_category`  | CharField(10)               | Classification LLM : `eval_n4`…`eval_n8`             |
| `rid7`           | CharField(20)               | Pivot vers django-crm (pas de FK)                    |
| `company_name`   | CharField(255)              | Nom de l'entreprise tel que publié                   |

**Contrainte d'unicité :** `unique_together = [("external_id", "source")]`

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

**Catégories d'évaluation (`eval_category`)** — remplies par le LLM classificateur :

| Code      | Libellé                          |
|:----------|:---------------------------------|
| `eval_n4` | Personnels d'exécution           |
| `eval_n5` | Techniciens, agents de maîtrise  |
| `eval_n6` | Managers opérationnels           |
| `eval_n7` | Cadres supérieurs                |
| `eval_n8` | Dirigeants / Executive           |

---

### RidetEntry

Entrée du registre officiel RIDET. Enrichie progressivement via Infogreffe et PDF RIDET.

| Champ                | Type           | Source              | Description                              |
|:---------------------|----------------|:--------------------|:-----------------------------------------|
| `rid7`               | CharField(20)  | CSV RIDET           | Numéro RIDET à 7 chiffres (unique)       |
| `denomination`       | CharField(255) | CSV / PDF           | Raison sociale officielle                |
| `sigle`              | CharField(100) | CSV / PDF           | Sigle ou abréviation                     |
| `enseigne`           | CharField(255) | CSV / PDF           | Nom commercial (enseigne)                |
| `date_etablissement` | DateField      | CSV RIDET           | Date de création de l'établissement      |
| `commune`            | CharField(100) | CSV / PDF RIDET     | Commune (ville)                          |
| `province`           | CharField(100) | CSV RIDET           | Province (Sud, Nord, Îles)               |
| `forme_juridique`    | CharField(100) | CSV / PDF           | SA, SARL, SAS, EURL, etc.               |
| `adresse`            | TextField      | Infogreffe          | Adresse complète                         |
| `code_naf`           | CharField(10)  | Infogreffe / PDF    | Code APE / NAF                           |
| `activite_principale`| TextField      | Infogreffe / PDF    | Libellé de l'activité principale         |
| `dirigeants`         | JSONField      | Infogreffe          | Liste de dirigeants (personne physique ou morale) |
| `description`        | TextField      | Manuel (frontend)   | Contexte éditorial — alimente les analyses IA |

> **Important** : `description` est saisie manuellement dans le frontend et ne doit **jamais**
> apparaître dans `update_fields` lors d'une mise à jour automatisée (consolidation, extraction PDF).

---

### AIAnalysis

Résultat d'une analyse LLM. Peut être lié à une offre ou à un rid7.

| Champ           | Type           | Description                                         |
|:----------------|----------------|:----------------------------------------------------|
| `job_offer`     | FK → JobOffer  | Nullable — analyse liée à une offre                 |
| `rid7`          | CharField(20)  | Nullable — analyse liée à une entreprise            |
| `analysis_type` | TextChoices    | Type d'analyse (voir ci-dessous)                    |
| `model_used`    | CharField(100) | Modèle Ollama utilisé                               |
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
| `eval_category`        | Classification niveau évaluation eval_n4…eval_n8   |

---

### PromptTemplate

Templates de prompts Ollama stockés en base et modifiables via l'admin Django.

| Champ        | Type              | Description                                       |
|:-------------|-------------------|:--------------------------------------------------|
| `name`       | SlugField         | Identifiant unique (ex. `skill_analysis`)         |
| `template`   | TextField         | Corps du prompt avec variables `{variable}`       |
| `is_system`  | BooleanField      | `True` = system prompt Ollama                     |
| `version`    | SmallIntegerField | Numéro de version                                 |

Les prompts sont chargés via des **data migrations** Django (pas via `load_prompts` au runtime).
Le service `_read_prompt(name)` cherche d'abord en base, puis se rabat sur le fichier `.txt`.

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
AppParameter.get("ai.model.general")              # → str | None
AppParameter.get("ai.model.general", "llama3.2")  # → str avec défaut
AppParameter.get_int("scraper.gouv_nc.limit", 50) # → int
AppParameter.get_float("scraper.delay", 1.0)      # → float
```

**Paramètres reconnus :**

| Clé                            | Défaut        | Description                               |
|:-------------------------------|:--------------|:------------------------------------------|
| `ai.model.general`             | (requis)      | Modèle Ollama principal (analyses, emails)|
| `ai.model.classifier`          | (requis)      | Modèle Ollama classificateur (rapide, temperature=0) |
| `ai.timeout`                   | `300`         | Timeout HTTP vers Ollama (secondes)       |
| `scraper.gouv_nc.limit`        | `50`          | Nombre max d'offres GOUV_NC               |
| `scraper.jobnc.anteriorite_jours` | `30`       | Fenêtre temporelle Job.nc (jours)         |
| `scraper.request_delay`        | `1.0`         | Délai entre requêtes scraper (s)          |

> `ai.model.general` et `ai.model.classifier` sont **obligatoires** — `_require_model()` lève
> une `RuntimeError` si absents. Les ajouter via l'admin ou l'API paramètres.

---

### JobSource

Table admin-éditable des sources d'offres d'emploi. Remplace le tuple `LEAD_SOURCE` hardcodé.

| Champ       | Type          | Description                                    |
|:------------|---------------|:-----------------------------------------------|
| `code`      | CharField(20) | Code interne (ex: `JOB_NC`) — unique           |
| `label`     | CharField(100)| Libellé affiché (ex: `Job.nc`)                 |
| `url`       | URLField      | URL du site source                             |
| `is_active` | BooleanField  | Si `False`, la source n'apparaît pas dans les filtres |

```python
JobSource.label_for("JOB_NC")  # → "Job.nc"
```

---

## 4. Services

### AIService (`services/ai_service.py`)

Wrapper autour de l'API REST Ollama cloud (`POST` vers `OLLAMA_CLOUD_URL`).
Requiert `OLLAMA_CLOUD_URL` et `OLLAMA_API_KEY` dans `.env.docker`.

```python
from iod_job_intel.services.ai_service import AIService

svc = AIService()

# Analyse des compétences critiques (retourne dict avec clé "critical_skills")
result = svc.analyze_offer(title, experience, skills, language)

# Diagnostic de l'offre (retourne str)
diagnostic = svc.diagnose_offer(title, location, description, experience, education, language)

# Questions brûlantes sur l'offre (retourne str)
questions = svc.generate_questions_brulantes_offre(
    title, education, description, skills, activities, company_context, language
)

# Questions brûlantes sur la capacité organisationnelle (retourne str)
questions = svc.generate_questions_brulantes(title, description, company_context, language)

# Email de prospection lié à une offre (retourne str)
email = svc.generate_email(title, source, contact_name, questions_brulantes, language)

# Email de prospection général (retourne str)
email = svc.generate_email_general(company_name, contact_name, questions_brulantes, language)

# Phrase d'accroche (retourne str)
ice = svc.generate_ice_breaker(company_name, job_title, language)

# Classification évaluation (retourne "eval_n4"…"eval_n8")
code = svc.classify_offer(title, description, qualification, experience)

# Extraction structurée d'un PDF Avis RIDET (retourne dict)
data = svc.extract_ridet_pdf(pdf_text)
```

**Résolution des modèles :**
- `svc.analyze_offer()`, `generate_*`, `diagnose_*` → `ai.model.general`
- `svc.classify_offer()`, `extract_ridet_pdf()` → `ai.model.classifier` (temperature=0.0)

**Résolution des prompts** (par ordre de priorité) :

1. `PromptTemplate.objects.get(name=<slug>)` — base de données (modifiable via admin)
2. `iod_job_intel/prompts/<slug>.txt` — fichier de fallback

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

Classe abstraite dont héritent tous les scrapers offres d'emploi.

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
- Paramètre `limit` : `AppParameter.get_int("scraper.gouv_nc.limit", 50)` (défaut 50)
- Format `external_id` : champ `identifiant` de l'API

---

### ProvinceSudScraper (`scrapers/province_sud.py`)

Source : emploi.province-sud.nc

**Passe 1** — collecte des identifiants depuis la page de liste HTML (regex `/offres/OF-YYYY-MM-NNN`)

**Passe 2** — détail via l'API Boost JSON `/api/offres/{id}`

---

### JobNCScraper (`scrapers/job_nc.py`)

Source : job.nc (Drupal CMS)

**Passe 1** — liste paginée, filtre par date de publication (fenêtre `days`)

**Passe 2** — page de détail HTML, extrait `node_id` depuis les classes CSS `<body>`

Format `external_id` : `JOB_NC-{node_id}`

---

### LemploiNCScraper (`scrapers/lemploi_nc.py`)

Source : lemploi.nc (Laravel + Inertia.js)

**Passe 1** — liste paginée, collecte slugs `/offres/{slug}`

**Passe 2** — détail via JSON-LD `JobPosting` + sidebar HTML

Format `external_id` : `LEMPLOI_NC-{id}`

---

### InfogreffeScraper (`scrapers/infogreffe_nc.py`)

Source : infogreffe.nc — données légales des entreprises.

Utilisé par l'endpoint `POST /ridet/<rid7>/consolidate/`.

- Recherche par rid7 → retourne dirigeants, adresse, code NAF, activité principale
- Les dirigeants peuvent être des `personne_physique` **ou** `personne_morale` (entreprises administratrices)
- Utilise Playwright + Browserless (SPA)

```python
from iod_job_intel.scrapers.infogreffe_nc import InfogreffeScraper

scraper = InfogreffeScraper()
data = scraper.fetch(rid7)
# → {"dirigeants": [...], "adresse": "...", "code_naf": "...", "activite_principale": "..."}
```

---

### AvisRidetScraper (`scrapers/avisridet_nc.py`)

Source : avisridet.isee.nc — PDF "Avis de situation RIDET".

Utilisé par l'endpoint `POST /ridet/<rid7>/extract-ridet/`.

- Le site est un SPA Next.js — requiert Playwright + Browserless
- Le PDF est servi via une API interne avec UUID dynamique : on intercepte l'URL de la réponse PDF,
  puis on la télécharge avec `requests` + cookies de session
- Le bandeau de consentement cookies est accepté automatiquement avant le clic de téléchargement
- Le RID7 doit être passé **sur 7 chiffres avec zéros de tête** (`.zfill(7)`) — ne jamais convertir en `int`

```python
from iod_job_intel.scrapers.avisridet_nc import AvisRidetScraper

scraper = AvisRidetScraper("0038380")
pdf_text = scraper.run()  # str (texte brut extrait via pdfplumber) ou None si non trouvé
```

---

## 6. API REST

Base URL : `/api/iod/`
Authentification : JWT Bearer Token (compatible django-crm)

### Offres d'emploi

```
GET  /api/iod/offers/                   Liste paginée
GET  /api/iod/offers/{id}/              Détail (avec description)
GET  /api/iod/offers/{id}/analyses/     Analyses IA liées
POST /api/iod/offers/{id}/start-action/ Déclencher une analyse IA sur une offre
POST /api/iod/offers/{id}/classify/     Classifier l'offre (eval_n4…eval_n8)
```

**Filtres disponibles :**

| Paramètre     | Exemple               | Description                              |
|:--------------|:----------------------|:-----------------------------------------|
| `rid7`        | `?rid7=1234567`       | Offres d'une entreprise                  |
| `source`      | `?source=JOB_NC`      | Par source                               |
| `status`      | `?status=PUBLIEE`     | Par statut                               |
| `q`           | `?q=développeur`      | Recherche fulltext titre + entreprise    |
| `eval_category` | `?eval_category=eval_n6` | Par catégorie évaluation            |

**`start-action` — actions disponibles :**

```json
{"action": "skill_analysis"}
{"action": "offer_diagnostic"}
{"action": "questions_offre"}
{"action": "questions_company"}
{"action": "email_job",     "contact_name": "M. Dupont", "language": "French"}
{"action": "email_general", "contact_name": "M. Dupont", "language": "French"}
{"action": "ice_breaker"}
```

---

### RIDET

```
GET  /api/iod/ridet/search/?q=...        Recherche (50 résultats max)
POST /api/iod/ridet/match/               Résolution nom → rid7
POST /api/iod/ridet/refresh/             Invalider le cache RidetService
GET  /api/iod/ridet/<rid7>/              Détail d'un établissement
POST /api/iod/ridet/<rid7>/consolidate/  Consolider via Infogreffe (dirigeants, adresse)
POST /api/iod/ridet/<rid7>/extract-ridet/ Consolider via PDF avisridet.isee.nc (LLM)
GET  /api/iod/ridet/<rid7>/crm-account/  Lien vers le compte CRM django-crm
POST /api/iod/ridet/<rid7>/ai/<action>/  Analyses IA sur l'entreprise
```

**Actions IA disponibles sur `/ridet/<rid7>/ai/<action>/` :**

| Action              | Prompt utilisé                 | Description                         |
|:--------------------|:-------------------------------|:------------------------------------|
| `questions_company` | `questions_brulantes_company`  | 7 questions brûlantes organisationnelles |
| `email_general`     | `email_prospect_general`       | Email de prospection général        |
| `ice_breaker`       | `ice_breaker`                  | Phrase d'accroche                   |

**Recherche RIDET :**

- Paramètre `q` obligatoire, minimum 2 caractères
- Recherche dans `denomination`, `enseigne`, `sigle`
- Retourne jusqu'à **50** résultats

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

---

### Paramètres de configuration

```
GET   /api/iod/parameters/                     Liste
GET   /api/iod/parameters/{key}/               Détail
PATCH /api/iod/parameters/{key}/               Mise à jour valeur
```

Les clés peuvent contenir des points (`ai.model.general`, `scraper.gouv_nc.limit`).

```bash
# Définir le modèle général
curl -X PATCH /api/iod/parameters/ai.model.general/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"value": "qwen3:latest"}'

# Définir le modèle classificateur
curl -X PATCH /api/iod/parameters/ai.model.classifier/ \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"value": "ministral-3b-cloud"}'
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

> En production, les prompts sont seedés via des **data migrations** Django. `load_prompts` est
> un outil de développement. Ne pas l'utiliser pour pousser des prompts modifiés — créer une
> migration à la place.

---

### `seed_eval_products` — Créer les produits évaluation

```bash
python manage.py seed_eval_products
```

Crée (ou met à jour) les produits CRM correspondant aux catégories d'évaluation `eval_n4`…`eval_n8`
dans django-crm. À exécuter une fois lors du premier déploiement.

> Utilise `get_set_context_sql()` pour définir le contexte RLS avant les écritures.

---

## 8. Templates de prompts

Les prompts sont définis dans `iod_job_intel/prompts/` et seedés en base via des **data migrations**.
Une fois en base, ils sont modifiables via l'interface d'administration Django sans redéploiement.

**Règle importante** : tout nouveau prompt ou renommage doit faire l'objet d'une migration de données
(`RunPython`) qui met à jour le `PromptTemplate` en base. Ne pas hardcoder de prompts dans le code Python.

| Fichier                          | Slug en base                     | Usage                                                  | Variables principales                                          |
|:---------------------------------|:---------------------------------|:-------------------------------------------------------|:---------------------------------------------------------------|
| `skill_analysis.txt`             | `skill_analysis`                 | 3 compétences critiques                                | `{title}`, `{experience}`, `{skills}`, `{language}`           |
| `offer_diagnostic.txt`           | `offer_diagnostic`               | Diagnostic qualitatif de l'offre                       | `{title}`, `{description}`, `{language}`                      |
| `classify_offer.txt`             | `classify_offer`                 | Classification eval_n4…eval_n8 (JSON)                  | `{context}`                                                    |
| `extract_ridet_pdf.txt`          | `extract_ridet_pdf`              | Extraction structurée d'un PDF Avis RIDET (JSON)       | `{pdf_text}`                                                   |
| `questions_brulantes_company.txt`| `questions_brulantes_company`    | 7 questions brûlantes sur la capacité organisationnelle| `{title}`, `{description}`, `{company_context}`, `{language}` |
| `questions_brulantes_offre.txt`  | `questions_brulantes_offre`      | 7 questions brûlantes sur les compétences requises     | `{title}`, `{education}`, `{description}`, `{skills}`, `{activities}`, `{company_context}`, `{language}` |
| `email_prospect_job.txt`         | `email_prospect_job`             | Email de prospection (offre spécifique)                | `{title}`, `{source}`, `{contact_name}`, `{questions_brulantes}`, `{language}` |
| `email_prospect_general.txt`     | `email_prospect_general`         | Email de prospection (entreprise)                      | `{company_name}`, `{contact_name}`, `{questions_brulantes}`, `{language}` |
| `ice_breaker.txt`                | `ice_breaker`                    | Phrase d'accroche email                                | `{company_name}`, `{job_title}`, `{language}`                 |
| `system_R6_I6_skills.txt`        | `system_R6_I6_skills`            | System prompt — 6 compétences individuelles            | *(system prompt, pas de variables)*                           |
| `system_R6_O6_capacities.txt`    | `system_R6_O6_capacities`        | System prompt — 6 capacités organisationnelles         | *(system prompt, pas de variables)*                           |

---

## 9. Installation dans django-crm

### Prérequis

```
Python 3.12+
beautifulsoup4==4.12.3
pyyaml==6.0.2
requests
pdfplumber==0.11.4        # extraction texte PDF
playwright                # scraping SPA (Browserless requis en Docker)
Ollama cloud              # OLLAMA_CLOUD_URL + OLLAMA_API_KEY
Browserless               # service Docker pour Playwright (ws://browserless:3000)
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

Dans `.env.docker` :

```dotenv
OLLAMA_CLOUD_URL=https://your-ollama-cloud-endpoint/api/generate
OLLAMA_API_KEY=your-api-key
OLLAMA_TIMEOUT=300
BROWSERLESS_WS=ws://browserless:3000
```

Dans `crm/settings.py` :

```python
OLLAMA_CLOUD_URL = os.environ.get("OLLAMA_CLOUD_URL", "")
OLLAMA_API_KEY   = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_TIMEOUT   = int(os.environ.get("OLLAMA_TIMEOUT", "300"))
BROWSERLESS_WS   = os.environ.get("BROWSERLESS_WS", "ws://browserless:3000")
```

### Étape 4 — Migrations

```bash
docker exec django-crm-backend-1 python manage.py migrate
```

Les migrations de données seedent automatiquement les prompts en base.

### Étape 5 — Données initiales

```bash
# Charger le référentiel RIDET
docker exec django-crm-backend-1 python manage.py load_ridet --url

# Créer les produits évaluation (une fois)
docker exec django-crm-backend-1 python manage.py seed_eval_products
```

### Étape 6 — Paramètres obligatoires

Depuis l'admin ou l'API, créer les deux paramètres AI :

```bash
# Via l'API
curl -X PATCH /api/iod/parameters/ai.model.general/ \
     -H "Authorization: Bearer <token>" \
     -d '{"value": "qwen3:latest"}'

curl -X PATCH /api/iod/parameters/ai.model.classifier/ \
     -H "Authorization: Bearer <token>" \
     -d '{"value": "ministral-3b-cloud"}'
```

### Étape 7 — Premier test de scraping

```bash
docker exec django-crm-backend-1 python manage.py run_sync --sources GOUV_NC --limit 10
```

---

## 10. Configuration

### Résolution des paramètres (ordre de priorité)

1. `AppParameter` (base de données) — modifiable à chaud via admin ou API
2. `django.conf.settings` (settings.py + variables d'environnement)
3. Valeur par défaut codée dans le service

### Discipline de configuration des prompts

1. Écrire le prompt dans `iod_job_intel/prompts/<slug>.txt`
2. Créer une migration de données `RunPython` qui seed/met à jour le `PromptTemplate` en base
3. Mettre à jour `AIService._read_prompt()` si un slug change (renommage)
4. En cas de renommage : migration qui update le `name` en base + mise à jour du code Python

**Ne jamais** hardcoder un prompt directement dans le code Python.

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
├── test_models.py    # Création, contraintes, méthodes de classe
├── test_services.py  # AnalysisService (score), RidetService (cache), AIService (mock Ollama)
└── test_api.py       # API REST complète — auth, filtres, pagination, détail, actions
```

---

## 12. Signaux

### `job_offer_created`

Signal personnalisé émis après la création d'une nouvelle offre **avec un rid7 connu**.

```python
from iod_job_intel.signals import job_offer_created

@receiver(job_offer_created)
def on_new_offer(sender, job_offer_id, rid7, title, company_name, score, **kwargs):
    account = Account.objects.filter(ridet=rid7).first()
    if account:
        Activity.objects.create(
            account=account,
            note=f"Nouvelle offre détectée : {title} (score {score})",
        )
```

---

## 13. Référence rapide

### Commandes Docker courantes

```bash
# Migrations
docker exec django-crm-backend-1 python manage.py migrate

# Données initiales
docker exec django-crm-backend-1 python manage.py load_ridet --url
docker exec django-crm-backend-1 python manage.py seed_eval_products

# Scraping
docker exec django-crm-backend-1 python manage.py run_sync --sources GOUV_NC --limit 10
docker exec django-crm-backend-1 python manage.py run_sync

# Tests
docker exec django-crm-backend-1 python -m pytest iod_job_intel/tests/ -v --no-cov
```

### Endpoints API résumés

| Méthode | URL                                      | Description                             |
|:--------|:-----------------------------------------|:----------------------------------------|
| GET     | `/api/iod/offers/`                       | Liste des offres (paginée)              |
| GET     | `/api/iod/offers/{id}/`                  | Détail d'une offre                      |
| GET     | `/api/iod/offers/{id}/analyses/`         | Analyses IA de l'offre                  |
| POST    | `/api/iod/offers/{id}/start-action/`     | Déclencher une analyse IA               |
| POST    | `/api/iod/offers/{id}/classify/`         | Classifier l'offre (eval_n4…n8)         |
| GET     | `/api/iod/ridet/search/?q=...`           | Recherche établissement RIDET (50 max)  |
| POST    | `/api/iod/ridet/match/`                  | Résolution nom → rid7                   |
| GET     | `/api/iod/ridet/<rid7>/`                 | Détail d'un établissement               |
| POST    | `/api/iod/ridet/<rid7>/consolidate/`     | Consolider via Infogreffe               |
| POST    | `/api/iod/ridet/<rid7>/extract-ridet/`   | Consolider via PDF avisridet.isee.nc    |
| GET     | `/api/iod/ridet/<rid7>/crm-account/`     | Lien vers le compte CRM                 |
| POST    | `/api/iod/ridet/<rid7>/ai/<action>/`     | Analyse IA sur l'entreprise             |
| GET     | `/api/iod/analyses/`                     | Liste des analyses IA                   |
| GET     | `/api/iod/logs/`                         | Journaux de scraping                    |
| GET     | `/api/iod/parameters/`                   | Paramètres de configuration             |
| PATCH   | `/api/iod/parameters/{key}/`             | Modifier un paramètre                   |
| POST    | `/api/iod/sync/trigger/`                 | Déclencher un scraping                  |

### Modèles résumés

| Modèle          | Rôle                                  | Clé naturelle            |
|:----------------|:--------------------------------------|:-------------------------|
| `JobOffer`      | Offre d'emploi                        | `(external_id, source)`  |
| `RidetEntry`    | Établissement NC (registre RIDET)     | `rid7`                   |
| `AIAnalysis`    | Résultat d'analyse LLM                | `(job_offer, type)` ou `(rid7, type)` |
| `PromptTemplate`| Template de prompt Ollama             | `name` (slug)            |
| `ScrapeLog`     | Journal de scraping                   | `(source, started_at)`   |
| `AppParameter`  | Configuration clé/valeur              | `key`                    |
| `JobSource`     | Sources d'offres (admin-éditable)     | `code`                   |
