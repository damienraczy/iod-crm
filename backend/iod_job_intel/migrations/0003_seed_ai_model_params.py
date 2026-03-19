"""
Migration de données : initialise les AppParameters pour les modèles IA Ollama cloud.
Les clés suivent la convention ai.model.<role>.
"""

from django.db import migrations


AI_MODEL_PARAMS = [
    ("ai.model.general", "gpt-oss:120b-cloud",    "Modèle général — analyses d'offres, emails, ice breakers"),
    ("ai.model.judge",   "llama3.2:latest",  "Modèle juge — évaluation qualité"),
    ("ai.model.thinking","qwen3.5:4b",       "Modèle raisonnement — questions complexes"),
    ("ai.model.rag",     "qwen3.5:4b",       "Modèle RAG — génération avec contexte"),
    ("ai.timeout",       "300",              "Timeout Ollama en secondes (cloud = lent, augmenter si besoin)"),
]


def seed_models(apps, schema_editor):
    AppParameter = apps.get_model("iod_job_intel", "AppParameter")
    for key, value, description in AI_MODEL_PARAMS:
        AppParameter.objects.update_or_create(
            key=key,
            defaults={"value": value, "description": description},
        )
    # Supprimer l'ancienne clé fourre-tout si elle existe
    AppParameter.objects.filter(key="ai.default_model").delete()


def unseed_models(apps, schema_editor):
    AppParameter = apps.get_model("iod_job_intel", "AppParameter")
    for key, value, description in AI_MODEL_PARAMS:
        AppParameter.objects.filter(key=key).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iod_job_intel", "0002_alter_joboffer_external_id_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_models, reverse_code=unseed_models),
    ]
