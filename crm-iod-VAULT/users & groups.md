`damien@iod.nc` : d@mien687

### Save & Restore

**Utilitaires** :
- `dam/export_groups_v2.py`
- `dam/restore_groups_v2.py`

**Sauvegarder :**
`docker compose exec -T backend python manage.py shell < dam/export_groups_v3.py`
docker compose exec -T backend python manage.py shell < dam/save_groups_v3.py
**Restaurer :**
`docker compose exec -T backend python manage.py shell < dam/restore_groups_v3.py`

**Note** :
Le fichier de données `groups_dump.json` sera généré à la racine du dossier `backend/` de votre projet.