import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class InfogreffeScraper:
    """
    Scraper pour Infogreffe.nc utilisant Browserless (Chromium distant).
    Cette méthode permet de gérer le rendu JavaScript (SPA) et de bypasser
    certaines protections anti-bot.
    """

    BASE_URL = "https://www.infogreffe.nc"
    BROWSERLESS_WS = os.environ.get("BROWSERLESS_WS", "ws://browserless:3000")

    def __init__(self, rid7: str):
        self.rid7 = str(rid7).strip().zfill(7)
        # Normalisation pour la recherche Infogreffe (souvent sans le 0 initial si présent)
        self.rid7_query = str(int(self.rid7))

    def run(self) -> Optional[Dict[str, Any]]:
        """Exécute le scraping via Playwright Remote."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Le module 'playwright' n'est pas installé dans le conteneur backend.")
            return None

        company_data = {}
        fonctions_data = {}
        # flag mutable partagé avec le handler pour activer la capture des dirigeants
        state = {"capture_fonctions": False}

        def _handle_response(response):
            try:
                if response.status != 200:
                    return
                if "json" not in response.headers.get("content-type", ""):
                    return
                rurl = response.url
                logger.debug(f"[Infogreffe] JSON intercepté : {rurl}")

                if "detail_entreprises" in rurl and "/fonctions" in rurl:
                    if state["capture_fonctions"]:
                        data = response.json()
                        if isinstance(data, dict) and "data" in data:
                            fonctions_data.update(data)

                elif "detail_entreprises" in rurl:
                    data = response.json()
                    if isinstance(data, dict) and data.get("id"):
                        company_data.update(data)
            except Exception:
                pass

        try:
            with sync_playwright() as p:
                logger.info(f"Connexion à Browserless pour RIDET {self.rid7}...")
                browser = p.chromium.connect_over_cdp(self.BROWSERLESS_WS)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.on("response", _handle_response)

                # --- Étape 1 : Recherche ---
                search_url = (
                    f"{self.BASE_URL}/recherche-entreprise-dirigeant/"
                    f"resultats-de-recherche?phrase={self.rid7_query}&type_entite=Entreprises"
                )
                logger.info(f"Navigation vers la recherche : {search_url}")
                page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(7000)

                # Chercher le lien vers la fiche détaillée (peut être présent même si
                # company_data est vide, car certaines entreprises ne déclenchent pas
                # l'appel detail_entreprises depuis la page de résultats)
                detail_link = None
                link_el = page.query_selector('a[href*="/entreprise/"]')
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        detail_link = href if href.startswith("http") else self.BASE_URL + href

                if not company_data and not detail_link:
                    logger.warning(
                        f"RID7 {self.rid7} : aucune donnée interceptée et aucun lien trouvé — "
                        f"entreprise absente d'Infogreffe.nc ou page sans résultat."
                    )
                    browser.close()
                    return None

                # --- Étape 2 : Détails (Dirigeants + company_data si absent de l'étape 1) ---
                if detail_link:
                    logger.info(f"Navigation vers la fiche : {detail_link}")
                    state["capture_fonctions"] = True
                    page.goto(detail_link, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(9000)

                if not company_data:
                    logger.warning(f"RID7 {self.rid7} : aucune donnée company après navigation sur la fiche.")
                    browser.close()
                    return None

                browser.close()

            return self._format_results(company_data, fonctions_data)

        except Exception as e:
            logger.error(f"Erreur Playwright Remote pour {self.rid7}: {e}")
            return None

    def _format_results(self, company_data: dict, fonctions_data: dict) -> dict:
        # Adresse
        addr_root = company_data.get("adresse") or {}
        declared = addr_root.get("adresse_declaree") or addr_root.get("adresse_redressee") or {}
        address = " ".join(
            p for p in [
                declared.get("ligne1", ""),
                declared.get("ligne2", ""),
                declared.get("ligne3", ""),
                declared.get("code_postal", ""),
                declared.get("bureau_distributeur", ""),
            ] if p
        ).strip()

        # Activité
        naf = company_data.get("activite_naf") or {}

        # Dirigeants
        managers = []
        for person in fonctions_data.get("data") or []:
            if not person.get("active", True):
                continue
            pp = person.get("personne_physique") or {}
            nom = pp.get("nom_usage") or pp.get("nom_patronymique", "")
            prenom = pp.get("premier_prenom", "")
            organe = person.get("organe") or {}
            qualite = (organe.get("qualite") or {}).get("libelle", "Dirigeant")
            if nom:
                managers.append(f"{prenom} {nom} ({qualite})".strip())

        return {
            "adresse": address,
            "code_naf": naf.get("code", ""),
            "activite_principale": naf.get("libelle", "") or company_data.get("activite_declaree", ""),
            "dirigeants": managers,
        }
