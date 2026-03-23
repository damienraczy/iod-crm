"""
Renomme le PromptTemplate questions_brulantes → questions_brulantes_company
et seed le nouveau fichier .txt.
"""
import os
from django.db import migrations


def rename_prompt(apps, schema_editor):
    PromptTemplate = apps.get_model("iod_job_intel", "PromptTemplate")
    txt_path = os.path.join(
        os.path.dirname(__file__), "..", "prompts", "questions_brulantes_company.txt"
    )
    with open(txt_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Renommer l'entrée existante si elle existe, sinon créer
    updated = PromptTemplate.objects.filter(name="questions_brulantes").update(
        name="questions_brulantes_company"
    )
    if not updated:
        PromptTemplate.objects.update_or_create(
            name="questions_brulantes_company",
            defaults={
                "description": "Questions brûlantes sur les capacités organisationnelles de l'entreprise",
                "template": template,
                "is_system": False,
                "version": 1,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("iod_job_intel", "0012_update_extract_ridet_pdf_prompt"),
    ]

    operations = [
        migrations.RunPython(rename_prompt, migrations.RunPython.noop),
    ]
