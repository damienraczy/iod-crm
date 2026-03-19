"""
Classe de base abstraite pour tous les scrapers iod_job_intel.

Fournit :
- Initialisation du ScrapeLog
- Réconciliation RIDET (_reconcile_company)
- Déduplication des offres (_save_offer via get_or_create)
- Finalisation du log (_finalize_log)
"""

import time
from typing import Optional

from django.utils import timezone

from iod_job_intel.models import JobOffer, ScrapeLog
from iod_job_intel.services.analysis_service import AnalysisService
from iod_job_intel.services.ridet_service import RidetService


class BaseScraper:
    """Classe de base pour les scrapers d'offres d'emploi NC."""

    source_id: str = ""          # À définir dans chaque sous-classe
    request_delay: float = 1.0   # Délai en secondes entre requêtes HTTP

    def __init__(self):
        if not self.source_id:
            raise NotImplementedError("source_id doit être défini dans la sous-classe")
        self.ridet_service    = RidetService()
        self.analysis_service = AnalysisService()
        self.log = ScrapeLog.objects.create(
            source=self.source_id,
            started_at=timezone.now(),
        )

    def run(self, **kwargs) -> dict:
        """Point d'entrée principal. À implémenter dans chaque sous-classe."""
        raise NotImplementedError

    def _reconcile_company(self, company_name: str) -> tuple[str, str]:
        """Recherche le RID7 du nom d'entreprise dans l'index RIDET.

        Retourne (rid7, company_name) — rid7 peut être vide si non trouvé.
        """
        rid7 = self.ridet_service.get_rid7_by_name(company_name) or ""
        return rid7, company_name

    def _save_offer(self, data: dict) -> Optional[JobOffer]:
        """Crée l'offre si elle n'existe pas déjà (déduplication par external_id + source).

        Retourne l'objet créé, ou None si l'offre existait déjà.
        """
        external_id = data.pop("external_id")
        source      = data.pop("source")

        obj, created = JobOffer.objects.get_or_create(
            external_id=external_id,
            source=source,
            defaults=data,
        )
        return obj if created else None

    def _sleep(self):
        """Respecte le délai de politesse entre requêtes HTTP."""
        time.sleep(self.request_delay)

    def _finalize_log(self, imported: int, skipped: int, error: str = ""):
        self.log.finalize(imported=imported, skipped=skipped, error=error)
