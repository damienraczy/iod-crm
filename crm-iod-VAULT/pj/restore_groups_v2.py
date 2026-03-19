import json
import os

from django.contrib.auth.models import Group, Permission


def restore_groups():
    input_path = "groups_dump.json"

    if not os.path.exists(input_path):
        print(f"--- ERROR: Fichier {input_path} introuvable ---")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for group_data in data:
        group, created = Group.objects.get_or_create(name=group_data["name"])
        status = "Créé" if created else "Mis à jour"

        perms_to_add = []
        for p_info in group_data["permissions"]:
            try:
                p = Permission.objects.get(
                    content_type__app_label=p_info["app_label"],
                    codename=p_info["codename"],
                )
                perms_to_add.append(p)
            except Permission.DoesNotExist:
                print(
                    f"  [!] Permission non trouvée: {p_info['app_label']}.{p_info['codename']}"
                )

        group.permissions.set(perms_to_add)
        print(
            f"--- {status}: Groupe '{group.name}' ({len(perms_to_add)} permissions) ---"
        )


if __name__ == "__main__":
    restore_groups()
