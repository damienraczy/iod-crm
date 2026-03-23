"""
Migration de données : seed du prompt extract_ridet_pdf dans PromptTemplate.
"""
import os
from django.db import migrations


def seed_prompt(apps, schema_editor):
    PromptTemplate = apps.get_model("iod_job_intel", "PromptTemplate")
    txt_path = os.path.join(
        os.path.dirname(__file__), "..", "prompts", "extract_ridet_pdf.txt"
    )
    with open(txt_path, "r", encoding="utf-8") as f:
        template = f.read()

    PromptTemplate.objects.update_or_create(
        name="extract_ridet_pdf",
        defaults={
            "description": "Extraction structurée JSON depuis un PDF Avis de situation RIDET (avisridet.isee.nc)",
            "template": template,
            "is_system": False,
            "version": 1,
        },
    )


def reverse_prompt(apps, schema_editor):
    PromptTemplate = apps.get_model("iod_job_intel", "PromptTemplate")
    PromptTemplate.objects.filter(name="extract_ridet_pdf").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("iod_job_intel", "0010_alter_ridetentry_activite_principale_textfield"),
    ]

    operations = [
        migrations.RunPython(seed_prompt, reverse_prompt),
    ]
