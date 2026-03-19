# docker ps
# Repérez le nom ou l'ID du conteneur qui fait tourner Django (souvent nommé web, app ou django).
# docker exec -i <nom_du_conteneur> python manage.py shell < <nom_du_script>

import os

from django.contrib.auth.models import Group


def export_crm_config():
    print("AUDIT DES GROUPES ET PERMISSIONS DJANGO-CRM\n")
    print("=" * 45 + "\n\n")

    groups = Group.objects.all().order_by("name")
    if not groups:
        print("Aucun groupe trouvé dans la base de données.\n")
        return

    for group in groups:
        print(f"GROUPE : {group.name}\n")
        print("-" * 20 + "\n")
        permissions = group.permissions.all().order_by(
            "content_type__app_label", "codename"
        )

        if not permissions:
            print("  (Aucune permission assignée)\n")
        else:
            for perm in permissions:
                # Format : [app_label] codename
                print(f"  [{perm.content_type.app_label}] {perm.codename}")
        print("\n")

    print("Export terminé")


# Exécution de la fonction
export_crm_config()
