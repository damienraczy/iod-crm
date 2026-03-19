# Déploiement — Django CRM + iod_job_intel sur A2Hosting VPS

Stack : Django · SvelteKit · PostgreSQL 16 · Redis · Docker Compose · Nginx · Let's Encrypt

---

## Prérequis A2Hosting

### Plan VPS recommandé
- **Runway 2** (2 Go RAM, 2 vCPU, 75 Go SSD) minimum — le backend Django + Postgres + Redis + Celery consomme ~900 Mo au repos.
- OS : **Ubuntu 22.04 LTS** (sélectionner lors de la commande).
- Activer l'accès SSH root depuis le panneau A2Hosting.

### DNS
Dans le gestionnaire DNS A2Hosting, créer deux enregistrements A :
```
crm.ton-domaine.nc   →  IP_DU_VPS
```
(Le frontend SvelteKit et l'API Django seront sur le même domaine, sous-chemins différents.)

---

## 1. Préparation du serveur

```bash
# Connexion initiale
ssh root@IP_DU_VPS

# Mise à jour système
apt update && apt upgrade -y

# Outils de base
apt install -y git curl vim ufw fail2ban

# Firewall
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable

# Utilisateur applicatif (ne pas déployer en root)
adduser deploy
usermod -aG sudo deploy
# Copier la clé SSH
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
```

---

## 2. Installation Docker

```bash
# Depuis le compte deploy
su - deploy

curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker deploy
# Se reconnecter pour activer le groupe
exit && ssh deploy@IP_DU_VPS

# Vérification
docker --version
docker compose version
```

---

## 3. Installation Nginx + Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
```

---

## 4. Récupérer le code

```bash
mkdir -p /srv/apps
cd /srv/apps
git clone https://github.com/damienraczy/django-crm.git
cd django-crm
```

---

## 5. Configuration de l'environnement production

Créer `.env.docker` (ne jamais commiter ce fichier avec les vraies valeurs) :

```bash
cp .env.docker .env.docker.bak   # garder l'exemple
vim .env.docker
```

Valeurs à modifier impérativement :

```env
# Django
SECRET_KEY=<générer avec : python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ENV_TYPE=prod
ALLOWED_HOSTS=crm.ton-domaine.nc,backend
DOMAIN_NAME=https://crm.ton-domaine.nc
SWAGGER_ROOT_URL=https://crm.ton-domaine.nc

# Base de données
DBNAME=crm_db
DBUSER=crm_user
DBPASSWORD=<mot_de_passe_fort>
DBHOST=db
DBPORT=5432
POSTGRES_DB=crm_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<mot_de_passe_fort_postgres>

# Redis / Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email (SMTP A2Hosting ou Office365)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=ton-smtp.exemple.nc
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=crm@exemple.nc
EMAIL_HOST_PASSWORD=<mot_de_passe_smtp>
DEFAULT_FROM_EMAIL=crm@exemple.nc
ADMIN_EMAIL=admin@exemple.nc
ADMIN_PASSWORD=<mot_de_passe_admin_django>

# CORS (production : domaine exact)
CORS_ALLOW_ALL=False
CORS_ALLOWED_ORIGINS=https://crm.ton-domaine.nc
CSRF_TRUSTED_ORIGINS=https://crm.ton-domaine.nc

# Frontend → Backend (interne Docker)
PUBLIC_DJANGO_API_URL=http://backend:8000

# Ollama cloud
OLLAMA_CLOUD_URL=https://ollama.com/api/generate
OLLAMA_API_KEY=<clé_ollama>
```

---

## 6. Build production SvelteKit

Le Dockerfile frontend utilise `pnpm dev` (mode développement). En production, il faut builder et servir le bundle compilé.

Créer `frontend/Dockerfile.prod` :

```dockerfile
FROM node:22-slim AS builder
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-slim
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json .
EXPOSE 3000
ENV NODE_ENV=production
CMD ["node", "build/index.js"]
```

Créer `docker-compose.prod.yml` (surcharge du docker-compose.yml de base) :

```yaml
services:
  db:
    ports: []   # pas d'exposition externe en prod

  redis:
    ports: []

  backend:
    ports: []
    command: >
      gunicorn crm.wsgi:application
        --bind 0.0.0.0:8000
        --workers 3
        --timeout 120

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    ports:
      - "3000:3000"
    volumes: []   # pas de volume en prod (code dans l'image)
```

Lancer en production :

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 7. Configuration Nginx

```bash
sudo vim /etc/nginx/sites-available/crm
```

```nginx
server {
    listen 80;
    server_name crm.ton-domaine.nc;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name crm.ton-domaine.nc;

    # SSL (rempli automatiquement par certbot)
    ssl_certificate     /etc/letsencrypt/live/crm.ton-domaine.nc/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/crm.ton-domaine.nc/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;

    client_max_body_size 20M;

    # API Django
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;   # pour les actions IA longues
    }

    # Admin Django
    location /admin/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # Fichiers statiques Django
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
    }

    # Frontend SvelteKit (tout le reste)
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/crm /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 8. SSL Let's Encrypt

```bash
# Le domaine doit déjà pointer vers l'IP du VPS (DNS propagé)
sudo certbot --nginx -d crm.ton-domaine.nc

# Renouvellement automatique (déjà configuré par certbot, vérifier)
sudo systemctl status certbot.timer
```

---

## 9. Premier démarrage

```bash
cd /srv/apps/django-crm

# Build et démarrage
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Suivre les logs du démarrage
docker compose logs -f backend

# Vérifier que les migrations ont tourné et l'admin créé
docker compose exec backend python manage.py showmigrations | tail -20

# Charger le RIDET (si base vide — prend ~5 min)
docker compose exec backend python manage.py load_ridet

# Vérifier
curl -s http://localhost:8000/api/ | head -5
curl -s http://localhost:3000 | head -3
```

---

## 10. Procédure de mise à jour

```bash
cd /srv/apps/django-crm

# 1. Récupérer le nouveau code
git pull iod master

# 2. Rebuild et redémarrer (zero-downtime approximatif)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Vérifier les logs
docker compose logs -f backend --tail=50
```

> Si la mise à jour inclut des migrations Django, elles s'appliquent automatiquement via l'`entrypoint.sh`.

---

## 11. Sauvegardes

### 11.1 Sauvegarde manuelle

```bash
# Créer le répertoire de sauvegardes
mkdir -p /srv/backups

# Base de données PostgreSQL
docker compose exec db pg_dump -U postgres crm_db | gzip \
  > /srv/backups/crm_db_$(date +%Y%m%d_%H%M%S).sql.gz

# Données Django (AppParameters, PromptTemplates, etc.)
docker compose exec backend python manage.py dumpdata \
  iod_job_intel.AppParameter \
  iod_job_intel.PromptTemplate \
  --indent 2 \
  > /srv/backups/iod_params_$(date +%Y%m%d).json

# Vérifier la taille
ls -lh /srv/backups/
```

### 11.2 Sauvegarde automatique (cron quotidien)

```bash
sudo vim /etc/cron.d/crm-backup
```

```cron
# Sauvegarde quotidienne à 3h00
0 3 * * * deploy /srv/apps/django-crm/scripts/backup.sh >> /var/log/crm-backup.log 2>&1
```

Créer `/srv/apps/django-crm/scripts/backup.sh` :

```bash
#!/bin/bash
set -e

BACKUP_DIR=/srv/backups
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR=/srv/apps/django-crm

# PostgreSQL
docker compose -f $APP_DIR/docker-compose.yml exec -T db \
  pg_dump -U postgres crm_db | gzip > $BACKUP_DIR/crm_db_$DATE.sql.gz

# Données clés
docker compose -f $APP_DIR/docker-compose.yml exec -T backend \
  python manage.py dumpdata iod_job_intel.AppParameter iod_job_intel.PromptTemplate \
  --indent 2 > $BACKUP_DIR/iod_params_$DATE.json

# Conserver 30 jours, supprimer les plus anciens
find $BACKUP_DIR -name "crm_db_*.sql.gz" -mtime +30 -delete
find $BACKUP_DIR -name "iod_params_*.json" -mtime +30 -delete

echo "[$DATE] Sauvegarde OK — $(ls $BACKUP_DIR | wc -l) fichiers"
```

```bash
chmod +x /srv/apps/django-crm/scripts/backup.sh
```

### 11.3 Transfert vers stockage distant (optionnel)

```bash
# Synchroniser vers un bucket S3 ou un serveur distant
# Installer rclone : https://rclone.org/install/
rclone sync /srv/backups remote:crm-backups/$(hostname)
```

---

## 12. Restauration

### 12.1 Restaurer la base PostgreSQL

```bash
# 1. Arrêter les services applicatifs (garder la DB)
docker compose stop backend celery-worker celery-beat frontend

# 2. Vider la base existante
docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS crm_db;"
docker compose exec db psql -U postgres -c "CREATE DATABASE crm_db OWNER crm_user;"

# 3. Restaurer depuis la sauvegarde
gunzip -c /srv/backups/crm_db_20250318_030000.sql.gz | \
  docker compose exec -T db psql -U postgres crm_db

# 4. Redémarrer
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 12.2 Restaurer les paramètres et prompts

```bash
docker compose exec backend python manage.py loaddata /srv/backups/iod_params_20250318.json
```

### 12.3 Réinstallation complète depuis zéro

Situation : nouveau VPS, tout est perdu sauf les fichiers de sauvegarde.

```bash
# 1. Préparer le serveur (étapes 1 à 3 ci-dessus)

# 2. Cloner le code
cd /srv/apps
git clone https://github.com/damienraczy/django-crm.git
cd django-crm

# 3. Recréer .env.docker avec les valeurs de production
vim .env.docker

# 4. Démarrer la DB seule d'abord
docker compose up -d db
sleep 5

# 5. Restaurer la base
gunzip -c /srv/backups/crm_db_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose exec -T db psql -U postgres crm_db

# 6. Démarrer tout le reste
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 7. Restaurer paramètres et prompts
docker compose exec backend python manage.py loaddata /chemin/vers/iod_params_YYYYMMDD.json

# 8. Reconfigurer Nginx + SSL (étapes 7 et 8)
```

---

## 13. Supervision

### Logs en temps réel
```bash
# Tous les services
docker compose logs -f

# Backend Django seulement
docker compose logs -f backend --tail=100

# Erreurs uniquement
docker compose logs backend 2>&1 | grep -E "ERROR|CRITICAL|Exception"
```

### Statut des containers
```bash
docker compose ps
```

### Utilisation des ressources
```bash
docker stats --no-stream
```

### Tester l'API depuis le serveur
```bash
# Sanity check
curl -s http://localhost:8000/api/ | python3 -m json.tool | head -10

# Vérifier que les offres sont accessibles (avec token)
curl -s http://localhost:8000/api/iod/offers/ -H "Authorization: Bearer <token>" | python3 -m json.tool | head -5
```

---

## 14. Dépannage fréquent

| Symptôme | Cause probable | Solution |
|---|---|---|
| 502 Bad Gateway | Container backend arrêté | `docker compose restart backend` |
| Migrations non appliquées | Entrypoint raté | `docker compose exec backend python manage.py migrate` |
| Fichiers statiques manquants | collectstatic non exécuté | `docker compose exec backend python manage.py collectstatic --noinput` |
| Timeout sur actions IA | Cloud Ollama lent | Augmenter `ai.timeout` dans les Paramètres |
| DB "connection refused" | Container db pas démarré | `docker compose up -d db` puis attendre le healthcheck |
| Certificat SSL expiré | Renouvellement certbot raté | `sudo certbot renew --force-renewal` |

---

## Récapitulatif des ports internes Docker

| Service | Port interne | Exposé sur l'hôte |
|---|---|---|
| backend (gunicorn) | 8000 | non (via nginx) |
| frontend (node) | 3000 | non (via nginx) |
| db (PostgreSQL) | 5432 | non |
| redis | 6379 | non |
| nginx | 80 / 443 | oui |
