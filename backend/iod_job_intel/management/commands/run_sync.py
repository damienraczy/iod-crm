"""
Commande de synchronisation manuelle des offres d'emploi.

Usage :
    python manage.py run_sync
    python manage.py run_sync --sources PSUD JOB_NC
    python manage.py run_sync --sources JOB_NC --days 7
    python manage.py run_sync --sources GOUV_NC --limit 100
"""

from django.core.management.base import BaseCommand


AVAILABLE_SOURCES = ["GOUV_NC", "PSUD", "JOB_NC", "LEMPLOI_NC"]


class Command(BaseCommand):
    help = "Synchronise les offres d'emploi depuis les sources configurées"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sources",
            nargs="+",
            choices=AVAILABLE_SOURCES,
            default=AVAILABLE_SOURCES,
            help="Sources à synchroniser (défaut : toutes)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Antériorité en jours pour JOB_NC (remplace AppParameter)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Nombre maximum d'offres par source",
        )

    def handle(self, *args, **options):
        sources = options["sources"]
        days    = options["days"]
        limit   = options["limit"]

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Synchronisation — sources : {', '.join(sources)}"
            )
        )

        total_imported = 0
        total_skipped  = 0

        if "GOUV_NC" in sources:
            self.stdout.write("→ GOUV_NC...")
            from iod_job_intel.scrapers.gouv_nc import GouvNCScraper
            stats = GouvNCScraper().run(limit=limit)
            total_imported += stats.get("imported", 0)
            total_skipped  += stats.get("skipped", 0)
            self.stdout.write(self.style.SUCCESS(
                f"  GOUV_NC : {stats.get('imported', 0)} importées, {stats.get('skipped', 0)} ignorées"
            ))

        if "PSUD" in sources:
            self.stdout.write("→ Province Sud...")
            from iod_job_intel.scrapers.province_sud import ProvinceSudScraper
            stats = ProvinceSudScraper().run(limit=limit)
            total_imported += stats.get("imported", 0)
            total_skipped  += stats.get("skipped", 0)
            self.stdout.write(self.style.SUCCESS(
                f"  PSUD : {stats.get('imported', 0)} importées, {stats.get('skipped', 0)} ignorées"
            ))

        if "JOB_NC" in sources:
            self.stdout.write("→ Job.nc...")
            from iod_job_intel.scrapers.job_nc import JobNCScraper
            kwargs = {}
            if days is not None:
                kwargs["days"] = days
            stats = JobNCScraper().run(**kwargs)
            total_imported += stats.get("imported", 0)
            total_skipped  += stats.get("skipped", 0)
            self.stdout.write(self.style.SUCCESS(
                f"  JOB_NC : {stats.get('imported', 0)} importées, {stats.get('skipped', 0)} ignorées"
            ))

        if "LEMPLOI_NC" in sources:
            self.stdout.write("→ L'Emploi.nc...")
            from iod_job_intel.scrapers.lemploi_nc import LemploiNCScraper
            stats = LemploiNCScraper().run(limit=limit)
            total_imported += stats.get("imported", 0)
            total_skipped  += stats.get("skipped", 0)
            self.stdout.write(self.style.SUCCESS(
                f"  LEMPLOI_NC : {stats.get('imported', 0)} importées, {stats.get('skipped', 0)} ignorées"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nTotal : {total_imported} importées, {total_skipped} ignorées"
        ))
