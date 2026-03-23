"""
Met à jour le prompt extract_ridet_pdf dans PromptTemplate (ajout du champ ville).
"""
import os
from django.db import migrations


def update_prompt(apps, schema_editor):
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
            "version": 2,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("iod_job_intel", "0011_seed_extract_ridet_pdf_prompt"),
    ]

    operations = [
        migrations.RunPython(update_prompt, migrations.RunPython.noop),
    ]
