# Maintenance, Mise à Jour et Réinstallation — iod_job_intel + Django-CRM

Ce document couvre trois procédures distinctes :
1. [Mettre à jour Django-CRM](maintenance_update_guide.md#1-mettre-à-jour-django-crm-sans-casser-iod_job_intel)
2. [Sauvegarder iod_job_intel](maintenance_update_guide.md#2-sauvegarder-iod_job_intel)
3. [Réinstaller iod_job_intel dans une nouvelle instance Django-CRM](maintenance_update_guide.md#3-réinstaller-iod_job_intel-dans-une-nouvelle-instance)

---

## Préambule : Principe d'Isolation

`iod_job_intel` est conçu pour ne **jamais** modifier le code source des applications natives de django-crm (`accounts`, `leads`, `contacts`, etc.). Les seuls fichiers natifs touchés sont :

| Fichier | Modification |
|---------|--------------|
| `backend/crm/settings.py` | 1 ligne dans `INSTALLED_APPS` + 3 lignes config Ollama (fin de fichier) |
| `backend/crm/urls.py` | 1 ligne `path("api/iod/", ...)` |
| `frontend/src/lib/components/layout/AppSidebar.svelte` | 4 icônes dans les imports + constante `iodItems` + section HTML "Intelligence" |

Tout le reste est **exclusif à notre customisation** et ne touche pas le code upstream.

---

## 1. Mettre à jour Django-CRM sans casser iod_job_intel

### Stratégie de branches Git (à mettre en place si ce n'est pas déjà fait)

La branche `master` doit rester identique à l'upstream officiel. Toutes les customisations vivent sur une branche `prod-custom`.

```
origin/master (upstream officiel MicroPyramid)
       ↓ git merge
prod-custom (notre installation customisée)
```

#### Mise en place initiale (une seule fois)

```bash
cd ~/dev/django-crm/django-crm

# Créer la branche prod-custom à partir de l'état actuel
git checkout -b prod-custom

# Vérifier que master pointe sur le upstream
git checkout master
git remote -v
# doit afficher : origin  https://github.com/MicroPyramid/django-crm.git
```

### Procédure de mise à jour

```bash
cd ~/dev/django-crm/django-crm

# 1. Mettre à jour le code upstream sur master (NE PAS être sur prod-custom)
git checkout master
git pull origin master

# 2. Basculer sur notre branche customisée
git checkout prod-custom

# 3. Merger les mises à jour upstream
git merge master
```

### Résolution des conflits attendus

Grâce à l'isolation, les seuls conflits possibles concernent les 3 fichiers listés ci-dessus.

#### Conflit dans `settings.py`

```bash
git status
# Affiche : both modified: backend/crm/settings.py
```

Ouvrir le fichier, chercher les marqueurs `<<<<<<< HEAD` :

```python
# Version upstream (garder telle quelle, c'est leur ajout)
<<<<<<< HEAD
    "leur_nouvelle_app",
=======
# Notre version (contient notre ligne iod_job_intel)
    "iod_job_intel",
>>>>>>> master
```

**Résolution :** Conserver les deux. Le fichier final doit avoir :
- Leurs ajouts upstream
- Notre ligne `"iod_job_intel",` en fin de `INSTALLED_APPS`
- Notre bloc Ollama en fin de fichier

```bash
# Vérifier que nos ajouts sont présents
grep -n "iod_job_intel\|OLLAMA" backend/crm/settings.py
# Doit afficher 4 lignes

# Marquer comme résolu
git add backend/crm/settings.py
```

#### Conflit dans `urls.py`

```bash
# Résoudre en conservant notre ligne path("api/iod/", ...)
# + leurs nouvelles routes éventuelles
grep "api/iod/" backend/crm/urls.py
# Doit afficher la ligne

git add backend/crm/urls.py
```

#### Conflit dans `AppSidebar.svelte`

C'est le conflit le plus probable car ce fichier contient la navigation et peut évoluer.

Chercher nos marqueurs dans le fichier :
```
// [IOD] iod_job_intel navigation icons
```
et
```
// [IOD] Section Intelligence Emploi — iod_job_intel
```

**Résolution :** Conserver leurs modifications UI + ré-insérer nos blocs marqués `[IOD]`.

```bash
git add frontend/src/lib/components/layout/AppSidebar.svelte
```

#### Finaliser le merge

```bash
git commit -m "Merge upstream master dans prod-custom"
```

### Après le merge : vérifications obligatoires

```bash
# Dans le conteneur Docker
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py check

# Vérifier que l'API IOD répond
curl -s http://localhost:8000/api/iod/offers/ | head -c 100
```

Si `python manage.py check` retourne des erreurs sur `iod_job_intel`, voir la section [Dépendances Python](maintenance_update_guide.md#dépendances-python).

---

## 2. Sauvegarder iod_job_intel

Une sauvegarde complète comprend : le code, les données, et les fichiers de configuration.

### 2.1 Sauvegarde du code

Le code est dans Git — il suffit que la branche `prod-custom` soit poussée sur un dépôt distant.

```bash
cd ~/dev/django-crm/django-crm

# Pousser prod-custom sur le remote (première fois : créer un fork privé sur GitHub)
git push origin prod-custom

# Ou vers un remote séparé (ex : dépôt privé)
git remote add custom git@github.com:votre-compte/django-crm-nc.git
git push custom prod-custom
```

**Fichiers exclusivement IOD à vérifier dans le commit :**

```
backend/iod_job_intel/          ← tout le répertoire
backend/crm/settings.py         ← nos 4 lignes
backend/crm/urls.py             ← notre 1 ligne
frontend/src/routes/(app)/job-intel/   ← tout le répertoire
frontend/src/lib/components/layout/AppSidebar.svelte
```

### 2.2 Sauvegarde de la base de données

#### Export complet des tables IOD (données opérationnelles)

```bash
# Dump de toutes les tables iod_job_intel
docker-compose exec db pg_dump \
  -U postgres \
  -d crm_db \
  --table="iod_job_intel_*" \
  -F c \
  -f /tmp/iod_backup_$(date +%Y%m%d).dump

# Copier le dump hors du conteneur
docker cp django-crm-db-1:/tmp/iod_backup_$(date +%Y%m%d).dump ~/backups/
```

#### Alternative via Django dumpdata (format JSON, plus portable)

```bash
docker-compose exec backend python manage.py dumpdata \
  iod_job_intel \
  --indent 2 \
  --output /tmp/iod_data_$(date +%Y%m%d).json

docker cp django-crm-backend-1:/tmp/iod_data_$(date +%Y%m%d).json ~/backups/
```

> **Important :** Le référentiel RIDET (~43 000 entrées) est volumineux. Il peut être rechargé depuis l'API officielle avec `load_ridet --url` plutôt que sauvegardé. Sauvegarder en priorité `AIAnalysis`, `JobOffer`, `AppParameter` et `PromptTemplate`.

#### Export sélectif (recommandé)

```bash
# Analyses IA (données précieuses, non recréables sans LLM)
docker-compose exec backend python manage.py dumpdata \
  iod_job_intel.AIAnalysis \
  iod_job_intel.PromptTemplate \
  iod_job_intel.AppParameter \
  --indent 2 \
  --output /tmp/iod_critical_$(date +%Y%m%d).json

docker cp django-crm-backend-1:/tmp/iod_critical_$(date +%Y%m%d).json ~/backups/
```

### 2.3 Sauvegarde des fichiers de configuration

```bash
# Copier les fichiers d'environnement (NE PAS mettre en Git)
cp ~/dev/django-crm/django-crm/.env.docker ~/backups/env.docker.backup
cp ~/dev/django-crm/django-crm/backend/.env ~/backups/env.backend.backup
```

### 2.4 Récapitulatif de sauvegarde complète

```bash
#!/bin/bash
# Script de sauvegarde iod_job_intel
DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR=~/backups/iod_$DATE
mkdir -p $BACKUP_DIR

# Code
cd ~/dev/django-crm/django-crm
git push origin prod-custom

# Données critiques
docker-compose exec backend python manage.py dumpdata \
  iod_job_intel.AIAnalysis \
  iod_job_intel.PromptTemplate \
  iod_job_intel.AppParameter \
  --indent 2 --output /tmp/iod_critical.json
docker cp django-crm-backend-1:/tmp/iod_critical.json $BACKUP_DIR/

# Config
cp .env.docker $BACKUP_DIR/
cp backend/.env $BACKUP_DIR/

echo "Sauvegarde complète dans $BACKUP_DIR"
```

---

## 3. Réinstaller iod_job_intel dans une nouvelle instance

Cette procédure part d'une **installation fraîche de django-crm** et y intègre notre module.

### Étape 0 : Installation fraîche de Django-CRM

```bash
cd ~/dev
git clone https://github.com/MicroPyramid/django-crm.git django-crm-new
cd django-crm-new

# Créer immédiatement la branche de customisation
git checkout -b prod-custom

# Copier les fichiers d'environnement
cp .env.example .env.docker   # si disponible, sinon créer manuellement

# Lancer Docker
docker-compose up -d --build

# Attendre que les conteneurs soient prêts (30 à 60 secondes)
docker-compose ps
# tous les services doivent être "Up"

# Migrations initiales django-crm
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

### Étape 1 : Copier le module iod_job_intel

#### Option A — depuis le dépôt Git (recommandé)

```bash
# Récupérer uniquement le répertoire iod_job_intel depuis prod-custom
git remote add custom git@github.com:votre-compte/django-crm-nc.git
git fetch custom

# Copier le répertoire via git archive
git archive custom/prod-custom backend/iod_job_intel | tar -x -C .

# Copier les routes frontend
git archive custom/prod-custom \
  frontend/src/routes/\(app\)/job-intel \
  | tar -x -C .
```

#### Option B — depuis une sauvegarde locale

```bash
cp -r ~/backups/iod_job_intel/ \
      ~/dev/django-crm-new/django-crm/backend/

cp -r ~/backups/job-intel/ \
      ~/dev/django-crm-new/django-crm/frontend/src/routes/\(app\)/
```

### Étape 2 : Modifier settings.py

Ouvrir `backend/crm/settings.py` et ajouter **à la fin de `INSTALLED_APPS`** et **à la fin du fichier** :

```python
# Dans INSTALLED_APPS, après les apps django-crm existantes :
INSTALLED_APPS = [
    ...
    # --- IOD Job Intelligence (scraping + IA offres d'emploi NC) ---
    "iod_job_intel",
]

# ---------------------------------------------------------------------------
# IOD Job Intelligence — configuration Ollama
# (ajouter EN FIN DE FICHIER pour faciliter les merges upstream)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL     = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_DEFAULT_MODEL = os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:latest")
OLLAMA_TIMEOUT      = int(os.environ.get("OLLAMA_TIMEOUT", "60"))
```

> **Règle :** Toujours ajouter **en fin de fichier**, jamais au milieu, pour minimiser les conflits lors des merges upstream.

### Étape 3 : Modifier urls.py

Ouvrir `backend/crm/urls.py` et ajouter la ligne IOD dans `urlpatterns` :

```python
urlpatterns = [
    # ... routes existantes django-crm ...
    path("api/iod/", include("iod_job_intel.api.urls")),   # [IOD] Intelligence Emploi
    # ... reste des routes ...
]
```

### Étape 4 : Installer les dépendances Python

Vérifier que `backend/requirements.txt` contient les lignes suivantes. Si non, les ajouter :

```
requests==2.32.5
beautifulsoup4==4.12.3
pyyaml==6.0.2
```

Puis reconstruire les conteneurs :

```bash
docker-compose down
docker-compose up -d --build
```

Si on ne veut pas reconstruire :

```bash
docker-compose exec backend pip install beautifulsoup4 requests pyyaml
docker-compose exec celery-worker pip install beautifulsoup4 requests pyyaml
```

### Étape 5 : Configurer les variables d'environnement

Ouvrir `.env.docker` et ajouter les variables Ollama :

```env
# IOD Job Intelligence — Ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_DEFAULT_MODEL=llama3.2:latest
OLLAMA_TIMEOUT=120
```

> `host.docker.internal` permet au conteneur Docker de joindre Ollama qui tourne sur le Mac hôte.
> Utiliser `http://localhost:11434` si Django tourne hors Docker.

### Étape 6 : Exécuter les migrations IOD

```bash
docker-compose exec backend python manage.py migrate iod_job_intel

# Vérifier que les tables sont créées
docker-compose exec backend python manage.py showmigrations iod_job_intel
# Doit afficher :
# iod_job_intel
#  [X] 0001_initial
#  [X] 0002_alter_joboffer_external_id_and_more
```

### Étape 7 : Charger le référentiel RIDET

Le RIDET est le registre officiel des ~43 000 établissements de Nouvelle-Calédonie.

```bash
# Import depuis l'API officielle (recommandé, prend 2-5 minutes)
docker-compose exec backend python manage.py load_ridet --url

# Ou depuis un fichier CSV local (si disponible dans sources/)
docker-compose exec backend python manage.py load_ridet \
  --csv sources/etablissements-actifs-au-ridet.csv
```

Vérification :

```bash
docker-compose exec backend python manage.py shell -c \
  "from iod_job_intel.models import RidetEntry; print(f'{RidetEntry.objects.count()} entrées RIDET')"
# Doit afficher : 43 000+ entrées RIDET
```

### Étape 8 : Charger les prompts IA

```bash
docker-compose exec backend python manage.py load_prompts

# Vérification
docker-compose exec backend python manage.py shell -c \
  "from iod_job_intel.models import PromptTemplate; print(list(PromptTemplate.objects.values_list('name', flat=True)))"
# Doit afficher les 9 noms de prompts
```

### Étape 9 : Restaurer les données sauvegardées (si migration)

```bash
# Copier le fichier de données dans le conteneur
docker cp ~/backups/iod_critical_YYYYMMDD.json django-crm-backend-1:/tmp/

# Charger les données (les AppParameter et PromptTemplate écrasent les valeurs par défaut)
docker-compose exec backend python manage.py loaddata /tmp/iod_critical_YYYYMMDD.json
```

> Si des erreurs de clés étrangères apparaissent, charger dans cet ordre :
> 1. `PromptTemplate`
> 2. `AppParameter`
> 3. `JobOffer` (si souhaité)
> 4. `AIAnalysis`

### Étape 10 : Mettre à jour la sidebar frontend

Ouvrir `frontend/src/lib/components/layout/AppSidebar.svelte`.

#### 10a. Ajouter les icônes aux imports

Localiser le bloc d'imports Lucide (chercher `from '@lucide/svelte'`) et ajouter :

```javascript
  Cloud,
  // [IOD] iod_job_intel navigation icons — ne pas supprimer lors des merges
  Newspaper,
  Search,
  Activity,
  SlidersHorizontal
} from '@lucide/svelte';
```

#### 10b. Ajouter la constante `iodItems`

Juste après la définition de `supportItems` et avant `const navigationItems` :

```javascript
  // [IOD] Section Intelligence Emploi — iod_job_intel — ne pas modifier lors des merges upstream
  const iodItems = [
    {
      key: 'job-intel',
      label: 'Intelligence Emploi',
      icon: Newspaper,
      type: 'dropdown',
      children: [
        { href: '/job-intel/offers', label: "Offres d'emploi", icon: Search, preload: 'off' },
        { href: '/job-intel/logs', label: 'Logs scraping', icon: Activity, preload: 'off' },
        { href: '/job-intel/parameters', label: 'Paramètres', icon: SlidersHorizontal, preload: 'off' }
      ]
    }
  ];

  const navigationItems = [...crmItems, ...salesItems, ...supportItems, ...iodItems];
```

#### 10c. Ajouter le bloc HTML de la section

Dans le template, juste **avant** le bloc `<!-- Support Section -->`, insérer le bloc HTML complet de la section "Intelligence". Ce bloc se trouve dans le commit Git de `prod-custom` — le copier intégralement.

Le marqueur à chercher dans la version de référence :
```html
<!-- [IOD] Intelligence Emploi Section — iod_job_intel -->
```

### Étape 11 : Test complet

```bash
# 1. Vérifier la santé Django
docker-compose exec backend python manage.py check
# Expected: System check identified no issues (0 silenced).

# 2. Lancer une synchronisation de test (5 offres GOUV_NC)
docker-compose exec backend python manage.py run_sync \
  --sources GOUV_NC --limit 5

# 3. Vérifier les offres importées
docker-compose exec backend python manage.py shell -c \
  "from iod_job_intel.models import JobOffer; print(f'{JobOffer.objects.count()} offres')"

# 4. Vérifier l'API REST
# (depuis le navigateur ou curl — nécessite un token JWT)
curl -s http://localhost:8000/api/iod/parameters/ \
  -H "Authorization: Bearer <votre_token>" | python -m json.tool

# 5. Ouvrir l'interface
# http://localhost:5173/job-intel/offers
```

---

## Référence rapide des fichiers modifiés dans django-crm

```
django-crm/
├── backend/
│   ├── crm/
│   │   ├── settings.py     ← +1 ligne INSTALLED_APPS + 3 lignes Ollama (fin fichier)
│   │   └── urls.py         ← +1 ligne path("api/iod/", ...)
│   ├── iod_job_intel/      ← NOTRE module (complet, ne pas fragmenter)
│   │   ├── api/
│   │   ├── management/
│   │   ├── migrations/
│   │   ├── models.py
│   │   ├── prompts/        ← 9 fichiers .txt de prompts
│   │   ├── scrapers/
│   │   ├── services/
│   │   └── signals.py
│   └── requirements.txt    ← +3 lignes (requests, beautifulsoup4, pyyaml)
└── frontend/
    ├── src/
    │   ├── lib/components/layout/
    │   │   └── AppSidebar.svelte   ← +4 icônes + iodItems + section HTML
    │   └── routes/(app)/
    │       └── job-intel/          ← NOTRE dossier (complet)
    │           ├── offers/
    │           │   ├── +page.svelte
    │           │   └── +page.server.js
    │           ├── logs/
    │           │   ├── +page.svelte
    │           │   └── +page.server.js
    │           └── parameters/
    │               ├── +page.svelte
    │               └── +page.server.js
```

## Dépendances Python

Trois packages requis en plus des dépendances django-crm standard :

| Package | Version | Usage |
|---------|---------|-------|
| `requests` | `2.32.5` | Appels HTTP vers Ollama et API GOUV_NC |
| `beautifulsoup4` | `4.12.3` | Parsing HTML des scrapers Province Sud, Job.nc, L'Emploi.nc |
| `pyyaml` | `6.0.2` | Lecture de fichiers YAML (migration depuis config.yaml) |

Ces packages sont dans `backend/requirements.txt`. Ils sont installés automatiquement lors du `docker-compose up --build`. En cas d'erreur `ModuleNotFoundError`, voir Étape 4.
