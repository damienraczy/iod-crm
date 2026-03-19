http://127.0.0.1:5173/login
http://127.0.0.1:8000/admin

voir quels conteneurs sont actifs et récupérer l'id d'un process :
- `docker-compose ps`

réinitialiser le password
- docker exec -it <process_id> python manage.py changepassword <user>

