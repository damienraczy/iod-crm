"""
Migration de données : initialise les 4 sources d'offres d'emploi Job Intel.
Ces entrées sont admin-éditables via /admin/iod_job_intel/jobsource/.
"""

from django.db import migrations


INITIAL_SOURCES = [
    {"code": "GOUV_NC",    "label": "Emploi Gouv NC",  "url": "https://www.emploi.gouv.nc"},
    {"code": "PSUD",       "label": "Province Sud",     "url": "https://www.province-sud.nc"},
    {"code": "JOB_NC",     "label": "Job.nc",           "url": "https://www.job.nc"},
    {"code": "LEMPLOI_NC", "label": "L'Emploi.nc",      "url": "https://www.lemploi.nc"},
]


def seed_sources(apps, schema_editor):
    JobSource = apps.get_model("iod_job_intel", "JobSource")
    for src in INITIAL_SOURCES:
        JobSource.objects.get_or_create(code=src["code"], defaults={
            "label": src["label"],
            "url":   src["url"],
            "is_active": True,
        })


def unseed_sources(apps, schema_editor):
    JobSource = apps.get_model("iod_job_intel", "JobSource")
    JobSource.objects.filter(code__in=[s["code"] for s in INITIAL_SOURCES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("iod_job_intel", "0005_jobsource_ridetentry_description"),
    ]

    operations = [
        migrations.RunPython(seed_sources, unseed_sources),
    ]
