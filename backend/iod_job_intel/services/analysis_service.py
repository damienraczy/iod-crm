"""
Service d'analyse et de scoring des offres d'emploi.

Adapté depuis src/analysis_service.py pour Django ORM.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List


class AnalysisService:
    """Calcul du score de priorité et détection de récurrence des offres."""

    def detect_recurrence(self, job_offer) -> List:
        """Détecte les offres similaires publiées par la même entreprise (2 ans glissants)."""
        from iod_job_intel.models import JobOffer

        if not job_offer.rid7:
            return []

        qs = (
            JobOffer.objects
            .exclude(pk=job_offer.pk)
            .filter(rid7=job_offer.rid7, location=job_offer.location)
            .filter(date_published__gte=datetime.now() - timedelta(days=730))
        )

        if job_offer.rome_code:
            qs = qs.filter(rome_code=job_offer.rome_code)
        else:
            qs = qs.filter(title__icontains=job_offer.title)

        return list(qs.order_by("-date_published"))

    def get_company_recruitment_intensity(self, rid7: str) -> Dict[str, Any]:
        """Analyse le volume et la diversité du recrutement d'une entreprise."""
        from iod_job_intel.models import JobOffer

        total_offers   = JobOffer.objects.filter(rid7=rid7).count()
        distinct_roles = (
            JobOffer.objects.filter(rid7=rid7)
            .values("title").distinct().count()
        )
        return {
            "total_offers":   total_offers,
            "distinct_roles": distinct_roles,
            "is_growing":     total_offers > 5 and distinct_roles > 3,
        }

    def calculate_score(self, offer) -> int:
        """Score de priorité (0-100) basé sur expérience, contrat, éducation, volume."""
        score = 0

        exp = (offer.experience_req or "").lower()
        if "5 ans" in exp or "10 ans" in exp:
            score += 30
        elif "2 ans" in exp or "3 ans" in exp:
            score += 15

        if offer.contract_type == "CDI":
            score += 20

        edu = (offer.education_req or "").lower().replace("+", "+ ").replace("+  ", "+ ")
        if "bac + 5" in edu or "master" in edu or "ingénieur" in edu:
            score += 20
        elif "bac + 3" in edu or "licence" in edu:
            score += 10

        if (offer.nb_postes or 1) > 1:
            score += 10

        return min(score, 100)
