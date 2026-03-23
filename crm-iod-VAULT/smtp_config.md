# Configuration SMTP - Django CRM

Cette notice explique comment configurer l'envoi d'e-mails pour l'application Django CRM tournant sous Docker.

## 1. Fichier de configuration cible
Dans un environnement Docker, **tous les changements** doivent être effectués dans le fichier suivant à la racine du projet :
`iod-crm/.env.docker`

> **Note :** Ne modifiez pas `backend/.env`, car il est ignoré par Docker au profit de `.env.docker`.

---

## 2. Paramètres pour A2 Hosting (Standard)

Voici la configuration validée pour votre compte **ext1@train.iod.nc** :

```env
# Email Backend
EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"

# Serveur SMTP (Hôte)
# Utilisez 'train.iod.nc' ou le nom du serveur A2 (ex: nl1-ss1.a2hosting.com)
EMAIL_HOST="train.iod.nc"

# Port (587 est recommandé pour TLS)
EMAIL_PORT="587"
EMAIL_USE_TLS="True"

# Identifiants
EMAIL_HOST_USER="ext1@train.iod.nc"
EMAIL_HOST_PASSWORD="your_password_here"

# Identité de l'expéditeur (CRUCIAL : doit correspondre à EMAIL_HOST_USER)
DEFAULT_FROM_EMAIL="ext1@train.iod.nc"
ADMIN_EMAIL="ext1@train.iod.nc"
```

---

## 3. Points d'attention majeurs

### A. Identité de l'expéditeur
La variable `DEFAULT_FROM_EMAIL` **doit** impérativement correspondre à `EMAIL_HOST_USER`. La plupart des serveurs SMTP (Office 365, A2 Hosting) rejettent les e-mails si l'adresse d'expédition déclarée est différente de l'adresse utilisée pour l'authentification.

### B. Résolution DNS dans Docker
Si vous obtenez l'erreur `gaierror: [Errno -2] Name or service not known`, cela signifie que le conteneur Docker n'arrive pas à résoudre l'adresse DNS de l'hôte SMTP. 
- Solution : Essayez d'utiliser l'adresse IP du serveur ou le nom technique du serveur A2 Hosting fourni dans votre cPanel (ex: `mi3-ss1.a2hosting.com`).

### C. Office 365 (Cas particulier)
Si vous repassez sur Office 365, assurez-vous que :
1. L'option **"SMTP authentifié"** est activée pour l'utilisateur dans le centre d'admin Microsoft 365.
2. Si la MFA est active, vous devez utiliser un **"Mot de passe d'application"**.

---

## 4. Application des changements
Chaque modification du fichier `.env.docker` nécessite un redémarrage des services pour être prise en compte par le moteur de tâches (Celery) :

```bash
docker-compose up -d celery-worker backend
```

---

## 5. Surveillance des logs
Pour vérifier si les e-mails partent réellement ou diagnostiquer une erreur SMTP :

```bash
docker logs -f iod-crm-celery-worker-1
```

Recherchez les lignes `Task common.tasks.send_magic_link_email... succeeded`.
