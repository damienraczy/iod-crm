import os

import django
from django.contrib.auth.models import Group, Permission


def setup_crm_groups():
    # Définition des permissions pour le groupe 'commercial'
    commercial_perms = [
        ("accounts", "add_account"),
        ("accounts", "add_accountemail"),
        ("accounts", "change_account"),
        ("accounts", "change_accountemail"),
        ("accounts", "view_account"),
        ("accounts", "view_accountemail"),
        ("cases", "add_case"),
        ("cases", "change_case"),
        ("cases", "view_case"),
        ("common", "add_activity"),
        ("common", "add_address"),
        ("common", "add_attachments"),
        ("common", "add_comment"),
        ("common", "add_commentfiles"),
        ("common", "add_document"),
        ("common", "add_magiclinktoken"),
        ("common", "add_tags"),
        ("common", "change_activity"),
        ("common", "change_address"),
        ("common", "change_attachments"),
        ("common", "change_comment"),
        ("common", "change_commentfiles"),
        ("common", "change_contactformsubmission"),
        ("common", "change_document"),
        ("common", "change_profile"),
        ("common", "change_tags"),
        ("common", "view_activity"),
        ("common", "view_address"),
        ("common", "view_attachments"),
        ("common", "view_comment"),
        ("common", "view_commentfiles"),
        ("common", "view_contactformsubmission"),
        ("common", "view_document"),
        ("common", "view_magiclinktoken"),
        ("common", "view_org"),
        ("common", "view_profile"),
        ("common", "view_tags"),
        ("contacts", "add_contact"),
        ("contacts", "change_contact"),
        ("contacts", "view_contact"),
        ("leads", "add_lead"),
        ("leads", "change_lead"),
        ("leads", "view_lead"),
        ("opportunity", "add_opportunity"),
        ("opportunity", "add_opportunitylineitem"),
        ("opportunity", "change_opportunity"),
        ("opportunity", "change_opportunitylineitem"),
        ("opportunity", "delete_opportunitylineitem"),
        ("opportunity", "view_opportunity"),
        ("opportunity", "view_opportunitylineitem"),
        ("tasks", "add_boardtask"),
        ("tasks", "add_task"),
        ("tasks", "change_boardtask"),
        ("tasks", "change_task"),
        ("tasks", "delete_task"),
        ("tasks", "view_board"),
        ("tasks", "view_boardcolumn"),
        ("tasks", "view_boardmember"),
        ("tasks", "view_boardtask"),
        ("tasks", "view_task"),
        ("tasks", "view_taskpipeline"),
        ("tasks", "view_taskstage"),
    ]

    # Définition des permissions supplémentaires pour le groupe 'responsable'
    responsable_extra_perms = [
        ("accounts", "delete_account"),
        ("accounts", "delete_accountemail"),
        ("cases", "delete_case"),
        ("common", "change_magiclinktoken"),
        ("common", "delete_activity"),
        ("common", "delete_address"),
        ("common", "delete_attachments"),
        ("common", "delete_comment"),
        ("common", "delete_commentfiles"),
        ("common", "delete_magiclinktoken"),
        ("common", "delete_tags"),
        ("contacts", "delete_contact"),
        ("leads", "add_leadpipeline"),
        ("leads", "add_leadstage"),
        ("leads", "change_leadpipeline"),
        ("leads", "change_leadstage"),
        ("leads", "delete_lead"),
        ("leads", "delete_leadpipeline"),
        ("leads", "delete_leadstage"),
        ("leads", "view_leadpipeline"),
        ("leads", "view_leadstage"),
        ("opportunity", "delete_opportunity"),
        ("tasks", "add_board"),
        ("tasks", "add_boardcolumn"),
        ("tasks", "add_boardmember"),
        ("tasks", "add_taskpipeline"),
        ("tasks", "add_taskstage"),
        ("tasks", "change_board"),
        ("tasks", "change_boardcolumn"),
        ("tasks", "change_boardmember"),
        ("tasks", "change_taskpipeline"),
        ("tasks", "change_taskstage"),
        ("tasks", "delete_board"),
        ("tasks", "delete_boardcolumn"),
        ("tasks", "delete_boardmember"),
        ("tasks", "delete_boardtask"),
        ("tasks", "delete_taskpipeline"),
        ("tasks", "delete_taskstage"),
    ]

    def assign_perms(group_name, perms_list):
        group, created = Group.objects.get_or_create(name=group_name)
        perms_to_add = []
        for app, code in perms_list:
            try:
                p = Permission.objects.get(content_type__app_label=app, codename=code)
                perms_to_add.append(p)
            except Permission.DoesNotExist:
                print(f"Attention : Permission introuvable -> {app}.{code}")

        group.permissions.set(perms_to_add)
        action = "créé" if created else "mis à jour"
        print(f"Groupe '{group_name}' {action} avec {len(perms_to_add)} permissions.")

    # Exécution pour les deux groupes
    assign_perms("commercial", commercial_perms)
    assign_perms("responsable", commercial_perms + responsable_extra_perms)


if __name__ == "__main__":
    setup_crm_groups()
