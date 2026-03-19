# Scraper Infogreffe.nc — Installation et réinstallation

## Pourquoi ce scraper est particulier

Infogreffe.nc est une Single Page Application (SPA) : les données (adresse, NAF, dirigeants) ne sont pas dans le HTML initial, elles arrivent via des appels JSON asynchrones déclenchés par le JavaScript de la page. On ne peut pas les récupérer avec un simple `requests.get()`.

La solution retenue : faire tourner un vrai navigateur Chromium piloté par Playwright, qui intercepte les réponses JSON au vol pendant la navigation. Le navigateur tourne dans un container Docker séparé (**Browserless**), le backend Django s'y connecte via le protocole CDP (Chrome DevTools Protocol) sur WebSocket.

---

## Architecture

```
Frontend SvelteKit
    │  POST /iod/ridet/<rid7>/consolidate/
    ▼
Backend Django (container backend)
    │  InfogreffeScraper.run()
    │  playwright.sync_api.connect_over_cdp("ws://browserless:3000")
    ▼
Browserless Chrome (container browserless)
    │  Ouvre un onglet Chromium
    │  Navigue sur infogreffe.nc
    │  Intercepte les réponses JSON de l'API Athena
    ▼
Infogreffe.nc (site externe)
    API interne : /detail_entreprises/<uuid>
                  /detail_entreprises/<uuid>/fonctions
```

Les données extraites sont enregistrées directement sur le `RidetEntry` correspondant dans la base de données PostgreSQL.

---

## Composants impliqués

| Composant | Rôle | Fichier/Service |
|---|---|---|
| `InfogreffeScraper` | Logique de scraping | `backend/iod_job_intel/scrapers/infogreffe_nc.py` |
| `RidetConsolidateView` | Endpoint API qui déclenche le scraper | `backend/iod_job_intel/api/views.py` |
| `RidetEntry` | Modèle Django qui stocke le résultat | `backend/iod_job_intel/models.py` |
| `browserless/chrome` | Chromium distant (container Docker) | `docker-compose.yml` → service `browserless` |
| `playwright==1.42.0` | Bibliothèque Python de pilotage | `backend/requirements.txt` |

---

## Installation initiale

### 1. Vérifier `requirements.txt`

Le package Playwright doit être présent :

```
# backend/requirements.txt
playwright==1.42.0
```

> **Important** : Playwright utilise ici `connect_over_cdp()` pour se connecter à un navigateur **distant**. Il ne lance pas de navigateur local. On n'a donc **pas besoin** de `playwright install chromium` dans le container backend — uniquement le package pip.

### 2. Vérifier `docker-compose.yml`

Le service `browserless` doit être présent :

```yaml
browserless:
  image: browserless/chrome:latest
  container_name: iod-crm-browserless
  restart: always
  ports:
    - "3000:3000"
  environment:
    - MAX_CONCURRENT_SESSIONS=5
    - CONNECTION_TIMEOUT=60000
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/pressure"]
    interval: 10s
    timeout: 5s
    retries: 5
```

> **Point de vigilance** : Le healthcheck correct est `/pressure`, pas `/ready`. `/ready` n'existe pas dans `browserless/chrome` et provoquerait un statut `unhealthy` permanent alors que le service fonctionne.

### 3. Builder et démarrer

```bash
# Depuis la racine du projet
docker compose build backend
docker compose up -d
```

### 4. Vérifier l'installation

#### a) Playwright installé dans le backend

```bash
docker exec iod-crm-backend-1 pip show playwright
# Doit afficher : Name: playwright, Version: 1.42.0
```

#### b) Browserless est healthy

```bash
docker compose ps
# La colonne STATUS du service browserless doit afficher "(healthy)"
```

En cas de doute, vérifier directement :

```bash
curl http://localhost:3000/pressure
# Réponse attendue : {"pressure":{"isAvailable":true,...}}
```

#### c) Connexion CDP backend → browserless

```bash
docker exec iod-crm-backend-1 python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('ws://browserless:3000')
    print('OK, version Chrome:', browser.version)
    browser.close()
"
# Doit afficher : OK, version Chrome: 121.x.x.x
```

Si cette commande échoue, le scraper échouera immédiatement à chaque appel.

---

## Réinstallation après ajout/modification de dépendances

Toute modification de `requirements.txt` nécessite un rebuild de l'image backend (le volume `./backend:/app` monte le code source, pas les packages pip) :

```bash
docker compose build backend
docker compose up -d backend celery-worker celery-beat
```

Vérifier ensuite que Playwright est bien présent :

```bash
docker exec iod-crm-backend-1 pip show playwright
```

---

## Fonctionnement du scraper

### Flux en deux étapes

**Étape 1 — Page de résultats de recherche**

```
GET https://www.infogreffe.nc/recherche-entreprise-dirigeant/resultats-de-recherche
    ?phrase=<rid7_sans_zero_initial>&type_entite=Entreprises
```

Le navigateur attend 7 secondes (`wait_for_timeout(7000)`) après `domcontentloaded` pour laisser le JavaScript faire ses appels API. Le handler intercepte la réponse JSON de l'endpoint `/detail_entreprises/<uuid>` pour récupérer nom, adresse, NAF.

En parallèle, le scraper cherche dans le DOM un lien `<a href*="/entreprise/">` pointant vers la fiche détaillée.

**Étape 2 — Fiche détaillée (dirigeants)**

Navigation sur l'URL de la fiche. Attente de 9 secondes. Le handler intercepte l'endpoint `/detail_entreprises/<uuid>/fonctions` pour récupérer la liste des dirigeants actifs.

### Normalisation du RID7

```python
rid7        = "0713172"  →  self.rid7 = "0713172" (zfill(7))
rid7_query  = "0713172"  →  self.rid7_query = "713172" (int() supprime le zéro initial)
```

Infogreffe.nc accepte le numéro sans zéro initial dans l'URL de recherche.

### Données extraites

| Champ | Source dans l'API Infogreffe |
|---|---|
| `adresse` | `adresse.adresse_declaree` (fallback : `adresse_redressee`) |
| `code_naf` | `activite_naf.code` |
| `activite_principale` | `activite_naf.libelle` (fallback : `activite_declaree`) |
| `dirigeants` | `fonctions.data[].personne_physique` + `organe.qualite.libelle` |

Seuls les dirigeants avec `"active": true` sont conservés (ou ceux sans le champ `active`, qui sont considérés actifs par défaut).

---

## Diagnostic et résolution des problèmes

### Erreur immédiate "Établissement non trouvé" sans délai

Le scraper retourne `None` instantanément. Causes possibles dans l'ordre de probabilité :

**1. Playwright non installé dans le container backend**

```bash
docker exec iod-crm-backend-1 pip show playwright
# Si "WARNING: Package(s) not found: playwright" → rebuild nécessaire
docker compose build backend && docker compose up -d backend celery-worker celery-beat
```

**2. Browserless injoignable ou crashé**

```bash
docker compose ps
# Vérifier le STATUS du service browserless

docker logs iod-crm-browserless --tail=20
# Chercher des erreurs de démarrage
```

Si le container tourne mais la connexion CDP échoue :

```bash
docker exec iod-crm-backend-1 python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('ws://browserless:3000')
    print('OK:', b.version)
    b.close()
"
```

**3. Variable d'environnement `BROWSERLESS_WS` incorrecte**

Par défaut le scraper utilise `ws://browserless:3000` (nom du service Docker). Si le service s'appelle différemment, définir dans `.env.docker` :

```
BROWSERLESS_WS=ws://mon-browserless:3000
```

### Logs détaillés pendant un scraping

Activer le niveau DEBUG pour voir toutes les URLs JSON interceptées :

```bash
docker logs iod-crm-backend-1 -f --tail=0
```

Puis déclencher la consolidation depuis l'interface. Les lignes `[Infogreffe] JSON intercepté :` apparaissent pour chaque réponse JSON capturée. Si aucune ligne n'apparaît contenant `detail_entreprises`, l'API Infogreffe a peut-être changé ses endpoints.

### Entreprise non trouvée malgré un scraper fonctionnel

Infogreffe.nc est le **registre du commerce** (Greffe du Tribunal Mixte de Commerce). Il ne couvre **pas** tous les établissements du RIDET. Les entreprises suivantes peuvent être absentes :

- Auto-entrepreneurs et professions libérales non immatriculées au RCS
- Associations (loi 1901)
- Établissements publics
- Certaines très petites structures artisanales

Dans ce cas, le message "Établissement non trouvé" est correct et attendu.

### Browserless marqué `unhealthy` mais fonctionnel

Vérifier que le healthcheck dans `docker-compose.yml` utilise `/pressure` et non `/ready` :

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000/pressure"]
```

Si le docker-compose a été corrigé, redémarrer le container pour appliquer le nouveau healthcheck :

```bash
docker compose up -d browserless
```

### L'image Browserless a changé de version

`browserless/chrome:latest` peut introduire des changements breaking entre versions. En cas de problème après une mise à jour d'image :

1. Épingler une version connue dans `docker-compose.yml` :
   ```yaml
   image: browserless/chrome:1.61-chrome-stable
   ```
2. Vérifier que l'endpoint CDP répond : `curl http://localhost:3000/pressure`
3. Tester la connexion CDP depuis le backend (voir ci-dessus)

---

## Checklist de vérification complète

```bash
# 1. Tous les containers tournent
docker compose ps

# 2. Playwright installé
docker exec iod-crm-backend-1 pip show playwright | grep Version

# 3. Browserless répond
curl http://localhost:3000/pressure

# 4. Connexion CDP OK
docker exec iod-crm-backend-1 python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('ws://browserless:3000')
    print('Chrome', b.version, '— connexion OK')
    b.close()
"

# 5. Test de scraping sur un RID7 connu (ex: Air Calédonie = 0000713)
docker exec iod-crm-backend-1 python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
django.setup()
from iod_job_intel.scrapers.infogreffe_nc import InfogreffeScraper
result = InfogreffeScraper('0000713').run()
print('Résultat:', result)
"
```

Si l'étape 5 retourne un dict avec `adresse`, `code_naf`, `dirigeants`, tout est opérationnel.
