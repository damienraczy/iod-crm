import json
import os

from django.contrib.auth.models import Group


def save_groups():
    data = []
    groups = Group.objects.all().prefetch_related("permissions__content_type")

    for group in groups:
        perms = []
        for p in group.permissions.all():
            perms.append(
                {"app_label": p.content_type.app_label, "codename": p.codename}
            )

        data.append({"name": group.name, "permissions": perms})

    # Chemin local au conteneur (/app/) qui correspond à votre dossier backend/
    output_path = "groups_dump.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"\n--- SUCCESS: {len(data)} groupes sauvegardés dans {output_path} ---")


# Appel direct obligatoire pour l'injection via redirection <
save_groups()
