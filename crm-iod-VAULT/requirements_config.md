# Dépendances Python : Module iod_job_intel

Si vous réinstallez l'application ou si vous l'ajoutez à une instance "standard" de Django-CRM, ces bibliothèques doivent être présentes dans votre environnement Python (ou `requirements.txt`).

## 1. Dépendances de base (Scraping & Parsing)
Nécessaires pour collecter et extraire les données des sites d'emploi calédoniens.

*   **`beautifulsoup4==4.12.3`** : Extraction de données HTML (utilisé par `Job.nc` et `Province Sud`).
*   **`requests==2.32.5`** : Requêtes HTTP pour l'API Gouv NC et le téléchargement des pages.
*   **`python-dateutil==2.9.0.post0`** : Manipulation complexe des dates de publication (formats variés selon les sources).

## 2. Dépendances IA & Configuration
Nécessaires pour l'analyse via Ollama et la gestion des prompts.

*   **`pyyaml==6.0.2`** : Lecture des fichiers de configuration et structuration des données.
*   **`requests`** (déjà cité) : Utilisé pour communiquer avec l'API locale d'Ollama (`http://localhost:11434`).

## 3. Dépendances Système (Optionnelles mais recommandées)
*   **`lxml`** : Si vous souhaitez accélérer le parsing HTML (BeautifulSoup l'utilisera s'il est présent, sinon il utilisera `html.parser` par défaut).

---

## Guide de mise à jour rapide (Docker)

Si vous rencontrez une erreur `ModuleNotFoundError` dans vos conteneurs, forcez la réinstallation ou la reconstruction :

### Option A : Installation à chaud (sans redémarrer)
```bash
docker exec -it django-crm-backend-1 pip install beautifulsoup4 pyyaml
docker exec -it django-crm-celery-worker-1 pip install beautifulsoup4 pyyaml
```

### Option B : Reconstruction propre (Recommandé)
Assurez-vous que ces lignes sont bien dans `backend/requirements.txt`, puis lancez :
```bash
docker-compose up -d --build
```
