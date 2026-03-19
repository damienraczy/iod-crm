"""
Scraper L'Emploi.nc (Laravel/Inertia, HTML + JSON-LD) — stratégie en deux passes.

Passe 1 : pages de listing → slugs des offres.
Passe 2 : pages de détail → JSON-LD + compléments HTML sidebar.

external_id : "LEMPLOI_NC-{id_numerique}" extrait du slug.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from iod_job_intel.models import AppParameter
from iod_job_intel.scrapers.base import BaseScraper


class LemploiNCScraper(BaseScraper):
    """Scraper des offres d'emploi lemploi.nc."""

    source_id          = "LEMPLOI_NC"
    request_delay      = 1.5
    LIST_URL           = "https://www.lemploi.nc/offres-d-emploi"
    DETAIL_URL_TEMPLATE = "https://www.lemploi.nc/offres-d-emploi/{}"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def run(self, limit: int = None, max_pages: int = 5, **kwargs) -> dict:
        if limit is None:
            limit = AppParameter.get_int("scraper.lemploinc.limit", 10)

        imported = 0
        skipped  = 0
        error    = ""

        try:
            slugs = self._collect_identifiers(max_pages=max_pages)
            if not slugs:
                print("[LEMPLOI_NC] Aucune offre identifiée.")
            else:
                to_process = slugs[:limit] if limit else slugs
                total      = len(to_process)
                for i, slug in enumerate(to_process):
                    print(f"\r[LEMPLOI_NC] {i+1}/{total} [{slug}]", end="", flush=True)
                    html = self._fetch_detail(slug)
                    if html:
                        offer_data = self._parse(html, slug)
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
            print(f"\n[LEMPLOI_NC] Erreur : {exc}")

        self._finalize_log(imported, skipped, error)
        print(f"[LEMPLOI_NC] importées={imported} ignorées={skipped}")
        return {"imported": imported, "skipped": skipped}

    def _collect_identifiers(self, max_pages: int = 5) -> List[str]:
        slugs: set = set()
        for page in range(1, max_pages + 1):
            print(f"\r[LEMPLOI_NC] Listing page {page}...", end="", flush=True)
            try:
                resp = requests.get(
                    self.LIST_URL, params={"page": page},
                    headers=self.HEADERS, timeout=20,
                )
                resp.raise_for_status()
                soup  = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/offres-d-emploi/" in href:
                        slug = href.split("/")[-1]
                        if slug and slug != "offres-d-emploi":
                            slugs.add(slug)
            except Exception as e:
                print(f"\n[LEMPLOI_NC] Erreur page {page} : {e}")
                break
            time.sleep(1)

        print(f"\n[LEMPLOI_NC] {len(slugs)} offres identifiées.")
        return list(slugs)

    def _fetch_detail(self, slug: str) -> Optional[str]:
        url = self.DETAIL_URL_TEMPLATE.format(slug)
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=20)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"\n[LEMPLOI_NC] Erreur fetch [{slug}] : {e}")
            return None

    @staticmethod
    def _clean_html(html_text: str) -> str:
        if not html_text:
            return ""
        return BeautifulSoup(html_text, "html.parser").get_text(separator="\n").strip()

    def _parse(self, html: str, slug: str) -> Optional[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Source de vérité : JSON-LD
        script_ld = soup.find("script", type="application/ld+json")
        data_ld: Dict[str, Any] = {}
        if script_ld:
            try:
                data_ld = json.loads(script_ld.string)
            except Exception:
                pass

        if not data_ld or data_ld.get("@type") != "JobPosting":
            return None

        external_id = f"LEMPLOI_NC-{slug.split('-')[-1]}"

        # Compléments sidebar HTML
        details: Dict[str, str] = {}
        sidebar = soup.find("section", class_=lambda x: x and "bg-secondary-100" in x)
        if sidebar:
            for p in sidebar.find_all("p", class_=lambda x: x and "text-sm" in x):
                icon = p.find("i")
                if not icon:
                    continue
                classes = " ".join(icon.get("class", []))
                text    = p.get_text(separator=" ", strip=True)
                if "fa-location-dot"  in classes:
                    details["location"] = text
                elif "fa-briefcase"   in classes:
                    details["contract"] = text
                elif "fa-business-time" in classes:
                    details["experience"] = text
                elif "fa-graduation-cap" in classes:
                    details["education"] = text
                elif "fa-calendar"    in classes:
                    details["date"] = text.replace("Publié le", "").strip()

        # Entreprise
        org          = data_ld.get("hiringOrganization") or {}
        company_name = org.get("name") or "Entreprise Anonyme"
        rid7, company_name = self._reconcile_company(company_name)

        # Date
        date_published = None
        if data_ld.get("datePosted"):
            try:
                date_published = datetime.fromisoformat(
                    data_ld["datePosted"]
                ).replace(tzinfo=None)
            except Exception:
                pass

        # Description
        raw_desc   = data_ld.get("description") or ""
        clean_desc = self._clean_html(raw_desc)

        # Type de contrat
        employment_type = data_ld.get("employmentType")
        contract_type   = details.get("contract") or (
            employment_type[0] if isinstance(employment_type, list) and employment_type else ""
        )

        # Localisation
        location = (
            details.get("location")
            or (data_ld.get("jobLocation") or {}).get("address", {}).get("addressLocality", "")
        )

        offer = {
            "external_id":   external_id,
            "source":        self.source_id,
            "title":         data_ld.get("title") or "Sans titre",
            "contract_type": contract_type,
            "location":      location,
            "experience_req": details.get("experience") or "",
            "education_req": details.get("education") or "",
            "nb_postes":     1,
            "date_published": date_published,
            "status":        "PUBLIEE",
            "description":   clean_desc,
            "raw_description": raw_desc,
            "url_external":  "",
            "skills_json":   [],
            "activities_json": [],
            "company_name":  company_name,
            "rid7":          rid7,
            "score":         0,
        }

        from iod_job_intel.models import JobOffer
        dummy = JobOffer(**{k: v for k, v in offer.items() if k not in ("external_id", "source")})
        offer["score"] = self.analysis_service.calculate_score(dummy)
        return offer
