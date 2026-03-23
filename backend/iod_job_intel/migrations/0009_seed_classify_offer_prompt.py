"""
Migration de données : initialise le PromptTemplate 'classify_offer'
pour la classification eval_n4→eval_n8 des offres d'emploi.
"""

from django.db import migrations

TEMPLATE = """\
Tu es un classificateur RH ultra-précis. Classifie l'offre d'emploi en UNE SEULE catégorie parmi les 5 suivantes :

- eval_n4 : Personnels d'exécution (opérateurs, ouvriers, employés)
- eval_n5 : Techniciens, agents de maîtrise, employés qualifiés
- eval_n6 : Managers opérationnels, responsables de service, cadres
- eval_n7 : Cadres supérieurs, responsables de département
- eval_n8 : Dirigeants / Executive (CODIR, DG)

{context}

Réponds EXCLUSIVEMENT avec un JSON valide et rien d'autre : {{"code": "eval_nX"}}
"""


def seed(apps, schema_editor):
    PromptTemplate = apps.get_model("iod_job_intel", "PromptTemplate")
    PromptTemplate.objects.update_or_create(
        name="classify_offer",
        defaults={
            "description": "Classificateur eval_n4→eval_n8 — température 0.0, modèle ai.model.classifier",
            "template": TEMPLATE,
            "is_system": False,
            "version": 1,
        },
    )


def unseed(apps, schema_editor):
    apps.get_model("iod_job_intel", "PromptTemplate").objects.filter(name="classify_offer").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iod_job_intel", "0008_seed_classifier_model"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
