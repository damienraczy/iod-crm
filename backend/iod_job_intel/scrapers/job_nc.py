"""
Scraper Job.nc (CMS Drupal, HTML) — stratégie en deux passes.

Passe 1 : pages de listing → slugs filtrés par date (antériorité configurable).
Passe 2 : pages de détail → données complètes (mission, profil, compétences).

external_id : "JOB_NC-{node_id}" (node Drupal, plus stable que le slug).
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from iod_job_intel.models import AppParameter
from iod_job_intel.scrapers.base import BaseScraper


class JobNCScraper(BaseScraper):
    """Scraper des offres d'emploi job.nc."""

    source_id          = "JOB_NC"
    request_delay      = 1.0
    LIST_URL           = "https://www.job.nc/offres"
    DETAIL_URL_TEMPLATE = "https://www.job.nc/offres/{}"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def run(self, days: int = None, **kwargs) -> dict:
        if days is None:
            days = AppParameter.get_int("scraper.jobnc.anteriorite_jours", 30)

        imported = 0
        skipped  = 0
        error    = ""

        try:
            listings = self._collect_recent_slugs(days)
            if not listings:
                print("[JOB_NC] Aucune offre récente.")
            else:
                total = len(listings)
                for i, listing in enumerate(listings):
                    slug = listing.get("slug")
                    if not slug:
                        skipped += 1
                        continue
                    print(f"\r[JOB_NC] {i+1}/{total} [{slug}]", end="", flush=True)
                    detail = self._fetch_detail(slug)
                    if detail:
                        offer_data = self._merge(listing, detail)
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
            print(f"\n[JOB_NC] Erreur : {exc}")

        self._finalize_log(imported, skipped, error)
        print(f"[JOB_NC] importées={imported} ignorées={skipped}")
        return {"imported": imported, "skipped": skipped}

    # ------------------------------------------------------------------ Passe 1

    def _collect_recent_slugs(self, days: int) -> List[Dict[str, Any]]:
        cutoff = datetime.now() - timedelta(days=days)
        print(f"[JOB_NC] Antériorité : {days} j (depuis {cutoff.date()})")
        results: List[Dict[str, Any]] = []
        page = 0

        while True:
            print(f"[JOB_NC] Page listing {page}...", end="", flush=True)
            try:
                resp = requests.get(
                    self.LIST_URL, params={"page": page},
                    headers=self.HEADERS, timeout=20,
                )
                resp.raise_for_status()
            except Exception as e:
                print(f" ERREUR : {e}")
                break

            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = self._parse_listing_cards(soup)
            if not cards:
                print(" (aucune carte — fin)")
                break

            print(f" {len(cards)} cartes")
            for card in cards:
                pub = card.get("date_published")
                if pub is None or pub >= cutoff:
                    results.append(card)

            last_pub = cards[-1].get("date_published")
            if last_pub and last_pub < cutoff:
                break

            page += 1
            time.sleep(1)

        print(f"[JOB_NC] {len(results)} offres récentes collectées.")
        return results

    def _parse_listing_cards(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        # Collecte des slugs via les liens "VOIR L'OFFRE"
        slugs: List[str] = []
        seen_slugs: set  = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).upper()
            href = a["href"]
            if "VOIR" in text and "OFFRE" in text and href.startswith("/offres/"):
                slug = href.split("/offres/")[-1]
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    slugs.append(slug)

        if not slugs:
            return []

        view = soup.find("div", class_="view-content")
        if not view:
            return []

        lines = [l.strip() for l in view.get_text(separator="\n").split("\n") if l.strip()]
        boundary_pattern = re.compile(r"voir\s+l[''`]offre", re.IGNORECASE)
        boundaries = [i for i, l in enumerate(lines) if boundary_pattern.search(l)]

        cards: List[Dict[str, Any]] = []
        for card_idx, boundary in enumerate(boundaries):
            start = boundaries[card_idx - 1] + 1 if card_idx > 0 else 0
            block = lines[start:boundary]
            card  = self._parse_card_block(block)
            if card and card_idx < len(slugs):
                card["slug"] = slugs[card_idx]
                cards.append(card)

        return cards

    def _parse_card_block(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        LABELS = {"Posté par :", "Lieu :", "Date :", "Type de contrat :"}
        data: Dict[str, Any] = {
            "titre": None, "entreprise": None, "lieu": None,
            "date_published": None, "contract_type": None,
        }
        label_pos: Dict[str, int] = {}
        for i, line in enumerate(lines):
            if line in LABELS:
                label_pos[line] = i

        if not label_pos:
            return None

        first_label_idx = min(label_pos.values())
        if first_label_idx > 0:
            data["titre"] = lines[0]

        def val_after(label: str) -> Optional[str]:
            idx = label_pos.get(label)
            if idx is not None and idx + 1 < len(lines):
                return lines[idx + 1]
            return None

        data["entreprise"]    = val_after("Posté par :")
        data["lieu"]          = val_after("Lieu :")
        data["contract_type"] = val_after("Type de contrat :")
        raw_date = val_after("Date :")
        if raw_date:
            try:
                data["date_published"] = datetime.strptime(raw_date.strip(), "%d/%m/%Y - %H:%M")
            except Exception:
                pass

        return data if data["titre"] else None

    # ------------------------------------------------------------------ Passe 2

    def _fetch_detail(self, slug: str) -> Optional[Dict[str, Any]]:
        url = self.DETAIL_URL_TEMPLATE.format(slug)
        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            return self._parse_detail_page(resp.text, slug)
        except Exception as e:
            print(f"\n[JOB_NC] Erreur détail [{slug}] : {e}")
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

    def _extract_field_value(self, soup: BeautifulSoup, css_name: str) -> str:
        for div in soup.find_all("div"):
            classes = " ".join(div.get("class") or [])
            if f"field-name-{css_name}" in classes:
                items = div.find_all("div", class_="field-item")
                if items:
                    return ", ".join(i.get_text(strip=True) for i in items if i.get_text(strip=True))
                label_el = div.find(class_="field-label")
                full_txt = div.get_text(separator=" ", strip=True)
                if label_el:
                    label_txt = label_el.get_text(strip=True)
                    if full_txt.startswith(label_txt):
                        return full_txt[len(label_txt):].strip()
                return full_txt
        return ""

    def _extract_field_html(self, soup: BeautifulSoup, css_name: str) -> str:
        for div in soup.find_all("div"):
            classes = " ".join(div.get("class") or [])
            if f"field-name-{css_name}" in classes:
                item = div.find("div", class_="field-item")
                if item:
                    return item.decode_contents()
                label_el = div.find(class_="field-label")
                if label_el:
                    label_el.decompose()
                return div.decode_contents()
        return ""

    def _parse_detail_page(self, html: str, slug: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        body         = soup.find("body")
        body_classes = " ".join(body.get("class") or []) if body else ""
        node_match   = re.search(r"page-node-(\d+)", body_classes)
        node_id      = node_match.group(1) if node_match else slug

        mission_html = self._extract_field_html(soup, "field-votre-mission")
        profil_html  = self._extract_field_html(soup, "field-votre-profil")
        mission_text = self._clean_html(mission_html)
        profil_text  = self._clean_html(profil_html)

        skills: List[str] = []
        if profil_html:
            psoup = BeautifulSoup(profil_html, "html.parser")
            for li in psoup.find_all("li"):
                t = li.get_text(strip=True)
                if t:
                    skills.append(t)
        if not skills:
            for line in profil_text.splitlines():
                line = line.strip()
                if line.startswith("•"):
                    skills.append(line.lstrip("• ").strip())

        niveau_formation  = self._extract_field_value(soup, "field-niveau-de-formation")
        annees_experience = self._extract_field_value(soup, "field-annees-d-experience")
        niveau_experience = self._extract_field_value(soup, "field-niveau")

        exp_parts = []
        if annees_experience:
            exp_parts.append(f"{annees_experience} ans")
        if niveau_experience:
            exp_parts.append(niveau_experience)
        experience_req = " - ".join(exp_parts) or None

        langues: List[str] = []
        for div in soup.find_all("div"):
            classes = " ".join(div.get("class") or [])
            if "field-name-field-langues" in classes:
                for item in div.find_all("div", class_="field-item"):
                    t = item.get_text(strip=True)
                    if t:
                        langues.append(t)
                break

        url_candidature: Optional[str] = None
        for div in soup.find_all("div"):
            classes = " ".join(div.get("class") or [])
            if "field-name-liens-offre" in classes:
                for a in div.find_all("a", href=True):
                    if a["href"].startswith("http"):
                        url_candidature = a["href"]
                        break
                break

        return {
            "node_id":       node_id,
            "mission_html":  mission_html,
            "mission_text":  mission_text,
            "profil_text":   profil_text,
            "skills":        skills,
            "education_req": niveau_formation or None,
            "experience_req": experience_req,
            "qualification": niveau_experience or None,
            "langues":       langues,
            "email":         self._extract_email(mission_text + " " + profil_text),
            "url_candidature": url_candidature,
        }

    # ------------------------------------------------------------------ Persistance

    def _merge(self, listing: Dict[str, Any], detail: Dict[str, Any]) -> Optional[dict]:
        node_id     = detail["node_id"]
        external_id = f"JOB_NC-{node_id}"

        company_name = (listing.get("entreprise") or "").strip() or "Anonyme JOB_NC"
        rid7, company_name = self._reconcile_company(company_name)

        description = detail["mission_text"]
        if detail["profil_text"]:
            description += "\n\nPROFIL RECHERCHÉ :\n" + detail["profil_text"]

        offer = {
            "external_id":   external_id,
            "source":        self.source_id,
            "title":         listing.get("titre") or "",
            "contract_type": listing.get("contract_type") or "",
            "location":      listing.get("lieu") or "",
            "experience_req": detail.get("experience_req") or "",
            "education_req": detail.get("education_req") or "",
            "qualification": detail.get("qualification") or "",
            "nb_postes":     1,
            "date_published": listing.get("date_published"),
            "status":        "PUBLIEE",
            "description":   description,
            "raw_description": detail.get("mission_html") or "",
            "url_external":  detail.get("url_candidature") or "",
            "skills_json":   detail.get("skills") or [],
            "activities_json": detail.get("langues") or [],
            "company_name":  company_name,
            "rid7":          rid7,
            "score":         0,
        }

        from iod_job_intel.models import JobOffer
        dummy = JobOffer(**{k: v for k, v in offer.items() if k not in ("external_id", "source")})
        offer["score"] = self.analysis_service.calculate_score(dummy)
        return offer
