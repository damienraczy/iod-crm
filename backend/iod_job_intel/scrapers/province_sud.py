"""
Scraper Province Sud (province-sud.nc) — stratégie en deux passes.

Passe 1 : collecte des identifiants OF-YYYY-MM-NNN depuis la page de recherche HTML.
Passe 2 : récupération du détail JSON par identifiant via l'API Boost.

external_id : "OF-YYYY-MM-NNN" (identifiant natif Province Sud).
"""

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from iod_job_intel.models import AppParameter
from iod_job_intel.scrapers.base import BaseScraper


class ProvinceSudScraper(BaseScraper):
    """Scraper des offres d'emploi Province Sud."""

    source_id          = "PSUD"
    request_delay      = 1.5
    BASE_URL           = "https://www.province-sud.nc/recherche"
    DETAIL_URL_TEMPLATE = "https://www.province-sud.nc/boostweb/boost/offre/OffreArticle/{}"

    HEADERS = {
        "User-Agent": "CRM-RH-Prospection-Bot/1.0 (+https://iod-ingenierie.nc)",
        "Accept":     "application/json, text/plain, */*",
    }

    def run(self, limit: int = None, **kwargs) -> dict:
        if limit is None:
            limit = AppParameter.get_int("scraper.psud.limit", 10)

        imported = 0
        skipped  = 0
        error    = ""

        try:
            identifiers = self._collect_identifiers()
            if not identifiers:
                print("[PSUD] Aucun identifiant collecté.")
            else:
                to_process = identifiers[:limit] if limit else identifiers
                total = len(to_process)
                print(f"[PSUD] {total} offres à traiter...")
                for i, ident in enumerate(to_process):
                    print(f"\r[PSUD] {i+1}/{total} [{ident}]", end="", flush=True)
                    detail = self._fetch_detail(ident)
                    if detail:
                        offer_data = self._parse(ident, detail)
                        if offer_data:
                            result = self._save_offer(offer_data)
                            if result:
                                imported += 1
                            else:
                                skipped += 1
                    self._sleep()
                print()
        except Exception as exc:
            error = str(exc)
            print(f"\n[PSUD] Erreur : {exc}")

        self._finalize_log(imported, skipped, error)
        print(f"[PSUD] importées={imported} ignorées={skipped}")
        return {"imported": imported, "skipped": skipped}

    def _collect_identifiers(self) -> List[str]:
        """Passe 1 : extrait les identifiants OF-YYYY-MM-NNN depuis la page de recherche."""
        params = {
            "categorieGenerale": "Offres d'emploi / Stages",
            "q": "offres,emploi",
        }
        try:
            resp = requests.get(
                self.BASE_URL, params=params, headers=self.HEADERS, timeout=20
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all(
                "a", href=re.compile(r"/boostweb/boost/offre/OffreArticle/OF-")
            )
            seen = []
            for a in links:
                ident = a["href"].split("/")[-1]
                if ident not in seen:
                    seen.append(ident)
            print(f"[PSUD] {len(seen)} identifiants collectés.")
            return seen
        except Exception as e:
            print(f"[PSUD] Échec collecte : {e}")
            return []

    def _fetch_detail(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Passe 2 : récupère le JSON de détail pour un identifiant."""
        url = self.DETAIL_URL_TEMPLATE.format(identifier)
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            data = resp.json()
            if data.get("success") and "data" in data:
                return data["data"]
        except Exception as e:
            print(f"\n[PSUD] Erreur détail [{identifier}] : {e}")
        return None

    @staticmethod
    def _clean_html(html_text: str) -> str:
        if not html_text:
            return ""
        return BeautifulSoup(html_text, "html.parser").get_text(separator=" ").strip()

    @staticmethod
    def _extract_email(text: str) -> Optional[str]:
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_url(html_text: str) -> Optional[str]:
        if not html_text:
            return None
        soup = BeautifulSoup(html_text, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("http"):
                return a["href"]
        return None

    def _parse(self, external_id: str, data: Dict[str, Any]) -> Optional[dict]:
        if not external_id:
            return None

        # Réconciliation entreprise
        raw_enseigne = data.get("enseigne") or "Anonyme PSUD"
        enseigne = raw_enseigne
        raison_sociale = None
        if "(" in raw_enseigne and ")" in raw_enseigne:
            enseigne = raw_enseigne[: raw_enseigne.find("(")].strip()
            raison_sociale = raw_enseigne[
                raw_enseigne.find("(") + 1 : raw_enseigne.find(")")
            ].strip()

        rid7 = self.ridet_service.get_rid7_by_name(enseigne)
        if not rid7 and raison_sociale:
            rid7 = self.ridet_service.get_rid7_by_name(raison_sociale)

        company_name = enseigne

        # Contenu
        modalities = data.get("modalitePresentation") or ""
        resume_clean = self._clean_html(data.get("resume"))
        savoirs = [
            s.strip("- ")
            for s in (data.get("savoir") or "").split("\r\n")
            if s.strip()
        ]
        savoir_faire = [
            s.strip("- ")
            for s in (data.get("savoirFaire") or "").split("\r\n")
            if s.strip()
        ]

        # Date : dérivée de l'identifiant (OF-YYYY-MM-NNN)
        date_published = None
        id_match = re.match(r"OF-(\d{4})-(\d{2})-\d+", external_id)
        if id_match:
            date_published = datetime(
                int(id_match.group(1)), int(id_match.group(2)), 1
            )

        offer = {
            "external_id":      external_id,
            "source":           self.source_id,
            "title":            data.get("titre") or "",
            "contract_type":    data.get("typeContratCode") or "",
            "location":         data.get("communeLocalisationLabel") or "",
            "experience_req":   "",
            "education_req":    "",
            "nb_postes":        1,
            "status":           "PUBLIEE" if data.get("offreStatutCode") == "ACTIVE" else "ARCHIVEE",
            "date_published":   date_published,
            "description":      resume_clean,
            "raw_description":  resume_clean,
            "url_external":     self._extract_url(modalities) or "",
            "skills_json":      savoir_faire,
            "activities_json":  savoirs,
            "company_name":     company_name,
            "rid7":             rid7 or "",
            "score":            0,
        }

        from iod_job_intel.models import JobOffer
        dummy = JobOffer(**{k: v for k, v in offer.items() if k not in ("external_id", "source")})
        offer["score"] = self.analysis_service.calculate_score(dummy)
        return offer
