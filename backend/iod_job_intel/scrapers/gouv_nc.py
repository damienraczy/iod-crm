"""
Scraper / importeur pour l'API officielle data.gouv.nc (GOUV_NC).

Utilise l'API OpenDataSoft v2.1 — dataset historique_emploi_gouv_nc.
Pas de scraping HTML : l'API retourne directement du JSON structuré.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from iod_job_intel.models import AppParameter
from iod_job_intel.scrapers.base import BaseScraper

API_URL = "https://data.gouv.nc/api/explore/v2.1/catalog/datasets/historique_emploi_gouv_nc/records"


class GouvNCScraper(BaseScraper):
    """Récupère et importe les offres depuis l'API officielle data.gouv.nc."""

    source_id = "GOUV_NC"

    def run(self, limit: int = None, **kwargs) -> dict:
        if limit is None:
            limit = AppParameter.get_int("scraper.gouv_nc.limit", 50)

        imported = 0
        skipped  = 0
        error    = ""

        try:
            records = self._fetch(limit)
            for entry in records:
                offer_data = self._parse(entry)
                if offer_data is None:
                    skipped += 1
                    continue
                result = self._save_offer(offer_data)
                if result:
                    imported += 1
                else:
                    skipped += 1
        except Exception as exc:
            error = str(exc)
            print(f"[GOUV_NC] Erreur : {exc}")

        self._finalize_log(imported, skipped, error)
        print(f"[GOUV_NC] importées={imported} ignorées={skipped}")
        return {"imported": imported, "skipped": skipped}

    def _fetch(self, limit: int) -> List[Dict[str, Any]]:
        params = {"order_by": "datepublication desc", "limit": limit}
        try:
            resp = requests.get(API_URL, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            raise RuntimeError(f"API GOUV_NC inaccessible : {e}") from e

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.replace(tzinfo=None)
        except Exception:
            return None

    def _parse(self, entry: Dict[str, Any]) -> Optional[dict]:
        external_id = entry.get("numero")
        if not external_id:
            return None

        company_name = entry.get("employeur_nomentreprise") or "Entreprise Anonyme"
        contact_email = entry.get("contact_mail")
        if company_name == "Anonyme" and contact_email:
            company_name = f"Anonyme ({contact_email})"

        rid7, company_name = self._reconcile_company(company_name)

        skills    = entry.get("competences_multievalue", []) or []
        activities = entry.get("activites_multievalue", []) or []

        from iod_job_intel.models import JobOfferStatus
        offer = {
            "external_id":      external_id,
            "source":           self.source_id,
            "title":            entry.get("titreoffre") or "",
            "rome_code":        entry.get("coderome") or "",
            "contract_type":    entry.get("typecontrat") or "",
            "location":         entry.get("communeemploi") or "",
            "experience_req":   entry.get("experience") or "",
            "education_req":    ", ".join(entry.get("niveauformation") or []),
            "nb_postes":        entry.get("nbpostes", 1) or 1,
            "date_published":   self._parse_date(entry.get("datepublication")),
            "status":           entry.get("statut") or JobOfferStatus.PUBLIEE,
            "description":      entry.get("description") or "",
            "raw_description":  entry.get("description") or "",
            "skills_json":      skills,
            "activities_json":  activities,
            "company_name":     company_name,
            "rid7":             rid7,
            "score":            0,
        }

        # Calcul du score — instanciation temporaire pour calculate_score
        from iod_job_intel.models import JobOffer
        dummy = JobOffer(**{k: v for k, v in offer.items() if k not in ("external_id", "source")})
        offer["score"] = self.analysis_service.calculate_score(dummy)

        return offer
