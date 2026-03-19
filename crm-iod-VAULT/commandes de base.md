### urls
http://127.0.0.1:5173/login
http://127.0.0.1:8000/admin

### voir quels conteneurs sont actifs et récupérer l'id d'un process :
- `docker-compose ps`

### réinitialiser le password
- docker exec -it <process_id> python manage.py changepassword <_ _user_ _>

### redémarrer
* `docker-compose stop && docker-compose start`

### Application des changements
Chaque modification du fichier `.env.docker` nécessite un redémarrage des services pour être prise en compte par le moteur de tâches (Celery) :

```bash
docker-compose up -d celery-worker backend
```



### Surveillance des logs
Pour vérifier si les e-mails partent réellement ou diagnostiquer une erreur SMTP :

```bash
docker logs -f django-crm-celery-worker-1
```

Recherchez les lignes `Task common.tasks.send_magic_link_email... succeeded`.
