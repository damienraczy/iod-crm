import logging
import requests
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from iod_job_intel.models import RidetEntry, AppParameter
from iod_job_intel.services.ridet_service import RidetService

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def _set_param(key, value, desc=""):
    AppParameter.objects.update_or_create(
        key=key, defaults={"value": str(value), "description": desc}
    )


@shared_task(name="iod_job_intel.tasks.refresh_ridet_task")
def refresh_ridet_task():
    """
    Télécharge et met à jour le référentiel RIDET depuis data.gouv.nc.
    Utilise AppParameter pour communiquer le statut au frontend.
    Traite les records par batchs de BATCH_SIZE pour allier performance
    et visibilité de la progression côté frontend.
    """
    _set_param("ridet_import_status", "RUNNING", "Statut de l'import RIDET (RUNNING, SUCCESS, FAILED)")
    _set_param("ridet_import_progress", "0", "Progression de l'import (%)")
    _set_param("ridet_import_error", "", "Dernière erreur d'import")

    EXPORT_URL = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/etablissements-actifs-au-ridet/exports/json"

    try:
        logger.info("Démarrage de l'import RIDET depuis data.gouv.nc...")
        resp = requests.get(EXPORT_URL, timeout=180)
        resp.raise_for_status()
        records = resp.json()

        total = len(records)
        if total == 0:
            raise ValueError("L'API a renvoyé 0 enregistrement.")

        logger.info(f"Traitement de {total} enregistrements RIDET...")
        created = updated = 0

        for batch_start in range(0, total, BATCH_SIZE):
            batch = records[batch_start:batch_start + BATCH_SIZE]

            with transaction.atomic():
                for r in batch:
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

                    _, was_created = RidetEntry.objects.update_or_create(
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

            # Mise à jour de la progression après chaque batch (hors transaction → visible immédiatement)
            progress = int(min(batch_start + BATCH_SIZE, total) / total * 100)
            _set_param("ridet_import_progress", progress)

        _set_param("ridet_import_status", "SUCCESS")
        _set_param("ridet_import_progress", "100")
        _set_param("ridet_last_import", timezone.now().isoformat())
        RidetService.invalidate_cache()

        logger.info(f"Import RIDET terminé : {created} créés, {updated} mis à jour.")
        return f"SUCCESS: {total} records processed."

    except Exception as e:
        logger.error(f"Erreur lors de l'import RIDET : {e}")
        _set_param("ridet_import_status", "FAILED")
        _set_param("ridet_import_error", str(e))
        return f"FAILED: {str(e)}"
