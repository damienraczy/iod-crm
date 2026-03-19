"""
Chargement initial des templates de prompts depuis les fichiers .txt.

Usage :
    python manage.py load_prompts
    python manage.py load_prompts --dir /chemin/vers/prompts/
    python manage.py load_prompts --overwrite   (écrase les entrées existantes)

Correspondance fichier → nom de PromptTemplate :
    skill_analysis.txt             → skill_analysis
    offer_diagnostic.txt           → offer_diagnostic
    questions_brulantes.txt        → questions_brulantes
    questions_brulantes_offre.txt  → questions_brulantes_offre
    email_prospect_job.txt         → email_prospect_job
    email_prospect_general.txt     → email_prospect_general
    ice_breaker.txt                → ice_breaker
    system_R6_I6_skills.txt        → system_R6_I6_skills       (is_system=True)
    system_R6_O6_capacities.txt    → system_R6_O6_capacities   (is_system=True)
"""

import os

from django.core.management.base import BaseCommand

DEFAULT_PROMPT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts"
)

SYSTEM_PROMPT_PREFIXES = ("system_",)


class Command(BaseCommand):
    help = "Charge les templates de prompts depuis les fichiers .txt dans PromptTemplate"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=DEFAULT_PROMPT_DIR,
            help="Répertoire contenant les fichiers .txt de prompts",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Écrase les templates existants",
        )

    def handle(self, *args, **options):
        from iod_job_intel.models import PromptTemplate

        prompt_dir = options["dir"]
        overwrite  = options["overwrite"]

        if not os.path.isdir(prompt_dir):
            self.stderr.write(f"Répertoire introuvable : {prompt_dir}")
            return

        txt_files = [f for f in os.listdir(prompt_dir) if f.endswith(".txt")]
        if not txt_files:
            self.stderr.write(f"Aucun fichier .txt dans {prompt_dir}")
            return

        created = 0
        skipped = 0
        updated = 0

        for filename in sorted(txt_files):
            name = filename[:-4]  # retire l'extension .txt
            is_system = any(name.startswith(p) for p in SYSTEM_PROMPT_PREFIXES)

            path = os.path.join(prompt_dir, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            existing = PromptTemplate.objects.filter(name=name).first()
            if existing:
                if overwrite:
                    existing.template  = content
                    existing.is_system = is_system
                    existing.version  += 1
                    existing.save()
                    updated += 1
                    self.stdout.write(f"  MAJ  : {name}")
                else:
                    skipped += 1
                    self.stdout.write(f"  SKIP : {name} (utiliser --overwrite pour écraser)")
            else:
                PromptTemplate.objects.create(
                    name=name,
                    description=f"Chargé depuis {filename}",
                    template=content,
                    is_system=is_system,
                )
                created += 1
                self.stdout.write(f"  CRÉÉ : {name}")

        self.stdout.write(self.style.SUCCESS(
            f"\nPrompts : {created} créés, {updated} mis à jour, {skipped} ignorés."
        ))
