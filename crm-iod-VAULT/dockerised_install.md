L'installation de **Django CRM** avec Docker sur macOS est la méthode la plus propre, car elle isole l'application et ses dépendances (base de données, serveur web) du reste de votre système.
## 1. Prérequis : Installer Docker Desktop
Docker Desktop est l'interface graphique qui gère les conteneurs sur Mac.
1. Téléchargez **Docker Desktop** sur le site officiel (docker.com).
2. Choisissez la version correspondant à votre processeur :
    - **Mac with Apple Chip** (M1, M2, M3, M4).
    - **Mac with Intel Chip**.
3. Installez l'application en faisant glisser l'icône dans votre dossier **Applications**.
4. Lancez Docker et attendez que l'icône de la baleine dans la barre de menu soit stable (ne clignote plus).

## 2. Étape 1 : Récupérer le code source
Ouvrez votre **Terminal** (via Spotlight ou dans Applications > Utilitaires) et tapez les commandes suivantes :
1. Placez-vous dans le dossier où vous souhaitez installer le projet (par exemple, le bureau) :
    `cd ~/dev/django-crm
2. Clonez le dépôt officiel :
    `git clone https://github.com/MicroPyramid/django-crm.git`
3. Entrez dans le dossier :
    `cd django-crm`

## 3. Étape 2 : Préparer l'environnement
Avant de lancer Docker, il est parfois nécessaire de créer un fichier de configuration pour les variables d'environnement. Dans le dossier `django-crm`, vérifiez s'il existe un fichier nommé `.env.example`.
- Faites une copie nommée `.env` :
    `cp .env.example .env` (si le fichier existe).
- Si le fichier n'existe pas, passez directement à l'étape suivante, le fichier `docker-compose.yml` utilisera les valeurs par défaut.

## 4. Étape 3 : Lancer l'installation avec Docker
C'est ici que Docker va télécharger les images nécessaires (Python, PostgreSQL, Redis) et configurer le réseau interne.
Tapez la commande suivante dans votre terminal :
`docker-compose up -d --build`
- **-d** : (detached) lance les conteneurs en arrière-plan.
- **--build** : force la construction des images à partir du code actuel.
> [!NOTE]
> 
> Le premier lancement peut prendre plusieurs minutes car Docker doit télécharger environ 1 Go de données.
---
## 5. Étape 4 : Initialiser la base de données
Une fois que les conteneurs sont "Up", vous devez créer les tables et le compte administrateur.
1. Exécutez les migrations (création des tables) :
    `docker-compose exec backend python manage.py migrate`
2. Créez votre compte administrateur :
    `docker-compose exec backend python manage.py createsuperuser`
    - Suivez les instructions dans le terminal pour choisir un identifiant, un email et un mot de passe.
---
## 6. Étape 5 : Accéder à la CRM
Ouvrez votre navigateur web et rendez-vous à l'adresse suivante :
- `http://localhost:8000/admin` pour l'administration
- `http://localhost:5173` pour le front end

Vous arriverez sur la page de connexion. Utilisez les identifiants créés à l'étape précédente.
---
### Commandes utiles pour la gestion quotidienne
| **Action**                          | **Commande**                     |
| ----------------------------------- | -------------------------------- |
| **Démarrer la CRM**                 | `docker-compose start`           |
| **Arrêter la CRM**                  | `docker-compose stop`            |
| **Voir les logs (en cas d'erreur)** | `docker-compose logs -f backend` |
| **Tout supprimer (nettoyage)**      | `docker-compose down`            |
Souhaitez-vous que je vous montre comment modifier le fichier de configuration pour lier vos modules d'import de données externes au conteneur Docker ?

### 7. Ajouter à `depends_on` 
depends_on doit contenir Browserless
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
      - PRE_VENT_INITIAL_DOWNLOAD=true
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/pressure"]
      interval: 10s
      timeout: 5s
      retries: 5
```

