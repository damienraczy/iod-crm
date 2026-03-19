"""
Chargement du référentiel RIDET depuis le fichier CSV officiel.

Usage :
    python manage.py load_ridet
    python manage.py load_ridet --csv /chemin/vers/etablissements.csv
    python manage.py load_ridet --url  (télécharge depuis data.gouv.nc)
"""

import csv
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "sources",
    "etablissements-actifs-au-ridet.csv"
)

API_URL = (
    "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/"
    "etablissements-actifs-au-ridet/records"
)


class Command(BaseCommand):
    help = "Charge le référentiel RIDET en base (depuis CSV ou API data.gouv.nc)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default=DEFAULT_CSV_PATH,
            help="Chemin vers le fichier CSV RIDET",
        )
        parser.add_argument(
            "--url",
            action="store_true",
            help="Télécharge les données depuis l'API d'export data.gouv.nc",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limite le nombre d'enregistrements à importer",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Vide la table avant l'import (import complet)",
        )

    def handle(self, *args, **options):
        from iod_job_intel.models import RidetEntry
        from iod_job_intel.services.ridet_service import RidetService

        limit = options.get("limit")

        if options["url"]:
            records = self._fetch_from_api(limit=limit)
        else:
            records = self._load_from_csv(options["csv"])
            if limit:
                records = records[:limit]

        if not records:
            raise CommandError("Aucun enregistrement à importer.")

        if options["clear"]:
            count, _ = RidetEntry.objects.all().delete()
            self.stdout.write(f"Table vidée ({count} entrées supprimées).")

        self.stdout.write(f"Import de {len(records)} établissements...")
        created = updated = 0

        for r in records:
            rid7 = r.get("rid7") or r.get("RID7")
            if not rid7:
                continue

            date_etab = None
            raw_date = r.get("date_etablissement") or r.get("dateetablissement")
            if raw_date:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                    try:
                        date_etab = datetime.strptime(str(raw_date)[:10], fmt).date()
                        break
                    except Exception:
                        pass

            obj, was_created = RidetEntry.objects.update_or_create(
                rid7=rid7,
                defaults={
                    "denomination":       (r.get("denomination") or "")[:255],
                    "sigle":              (r.get("sigle") or "")[:100],
                    "enseigne":           (r.get("enseigne") or "")[:255],
                    "date_etablissement": date_etab,
                    "commune":            (r.get("commune") or "")[:100],
                    "province":           (r.get("province") or "")[:100],
                    "forme_juridique":    (r.get("forme_juridique") or r.get("formejuridique") or "")[:100],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Invalider le cache mémoire
        RidetService.invalidate_cache()

        self.stdout.write(self.style.SUCCESS(
            f"RIDET chargé : {created} créés, {updated} mis à jour."
        ))

    def _load_from_csv(self, csv_path: str):
        if not os.path.exists(csv_path):
            raise CommandError(f"Fichier CSV introuvable : {csv_path}")
        self.stdout.write(f"Lecture CSV : {csv_path}")
        with open(csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _fetch_from_api(self, limit=None):
        import requests
        self.stdout.write("Téléchargement de l'export depuis data.gouv.nc...")
        # L'API d'export permet de télécharger tout sans limite d'offset
        EXPORT_URL = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/etablissements-actifs-au-ridet/exports/json"
        
        params = {}
        if limit:
            params["limit"] = limit
            
        try:
            resp = requests.get(EXPORT_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            raise CommandError(f"Erreur lors de l'export API RIDET : {e}")
