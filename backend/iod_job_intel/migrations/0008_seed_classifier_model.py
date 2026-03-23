"""
Migration de données : initialise AppParameter ai.model.classifier
pour le modèle LLM de classification des offres d'emploi.
"""

from django.db import migrations


def seed(apps, schema_editor):
    AppParameter = apps.get_model("iod_job_intel", "AppParameter")
    AppParameter.objects.update_or_create(
        key="ai.model.classifier",
        defaults={
            "value": "ministral-3b-cloud",
            "description": "Modèle classificateur — catégorisation eval_n4→eval_n8 (temperature 0.0)",
        },
    )


def unseed(apps, schema_editor):
    AppParameter = apps.get_model("iod_job_intel", "AppParameter")
    AppParameter.objects.filter(key="ai.model.classifier").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iod_job_intel", "0007_joboffer_eval_category"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
