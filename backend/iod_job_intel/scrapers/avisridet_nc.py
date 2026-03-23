"""
Scraper pour avisridet.isee.nc — télécharge le PDF "Avis de situation RIDET"
et en extrait le texte brut via pdfplumber.

Utilise Playwright + Browserless (comme InfogreffeScraper) car le site est un SPA Next.js.
Le PDF est servi via une API interne avec UUID dynamique :
on intercepte l'URL de la réponse PDF, puis on la télécharge avec requests + cookies.

Usage :
    scraper = AvisRidetScraper("0111559")
    pdf_text = scraper.run()  # str ou None si non trouvé
"""
import io
import logging
import os

import requests as _requests

logger = logging.getLogger(__name__)

BROWSERLESS_WS = os.environ.get("BROWSERLESS_WS", "ws://browserless:3000")
BASE_URL = "https://avisridet.isee.nc"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class AvisRidetScraper:
    def __init__(self, rid7: str):
        self.rid7 = str(rid7).strip()
        # Le site avisridet.isee.nc attend le numéro à 7 chiffres exact (avec zéros de tête)
        self.rid7_query = self.rid7.zfill(7)

    def run(self) -> str | None:
        """
        Ouvre la page de résultats, clique sur le bouton de téléchargement
        de la première ligne, intercepte l'URL du PDF, le télécharge et
        retourne le texte extrait.
        """
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("pdfplumber n'est pas installé.")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("playwright n'est pas installé.")

        pdf_url = None
        cookies_dict = {}

        try:
            with sync_playwright() as p:
                logger.info(f"AvisRidet: connexion à Browserless pour RID7 {self.rid7}")
                browser = p.chromium.connect_over_cdp(BROWSERLESS_WS)
                context = browser.new_context(user_agent=USER_AGENT, accept_downloads=True)
                page = context.new_page()

                def handle_response(response):
                    nonlocal pdf_url
                    ct = response.headers.get("content-type", "")
                    if "application/pdf" in ct and pdf_url is None:
                        pdf_url = response.url
                        logger.info(f"AvisRidet: URL PDF capturée — {pdf_url}")

                page.on("response", handle_response)

                search_url = f"{BASE_URL}/?search={self.rid7_query}"
                logger.info(f"AvisRidet: navigation vers {search_url}")
                page.goto(search_url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)

                dl_btn = page.query_selector(".pi-download")
                if not dl_btn:
                    logger.warning(f"AvisRidet: aucun résultat pour RID7 {self.rid7}")
                    browser.close()
                    return None

                # Accepter le bandeau cookies s'il est présent
                try:
                    accept_btn = page.get_by_text("Tout accepter", exact=True)
                    if accept_btn.is_visible(timeout=2000):
                        accept_btn.click()
                        page.wait_for_timeout(1000)
                        logger.info("AvisRidet: bandeau cookies accepté")
                except Exception:
                    pass  # Pas de bandeau, on continue

                logger.info("AvisRidet: clic sur le premier bouton de téléchargement")
                dl_btn.click()
                page.wait_for_timeout(8000)

                # Récupérer les cookies de session pour le re-download
                for c in context.cookies():
                    cookies_dict[c["name"]] = c["value"]

                browser.close()

        except Exception as e:
            logger.error(f"AvisRidet: erreur Playwright pour {self.rid7}: {e}")
            return None

        if not pdf_url:
            logger.warning(f"AvisRidet: aucune URL PDF interceptée pour {self.rid7}")
            return None

        # Télécharger le PDF avec requests (hors Playwright)
        logger.info(f"AvisRidet: téléchargement du PDF via requests — {pdf_url}")
        try:
            resp = _requests.get(
                pdf_url,
                headers={"User-Agent": USER_AGENT, "Referer": BASE_URL},
                cookies=cookies_dict,
                timeout=30,
            )
            resp.raise_for_status()
            pdf_bytes = resp.content
            logger.info(f"AvisRidet: PDF téléchargé ({len(pdf_bytes)} bytes)")
        except Exception as e:
            logger.error(f"AvisRidet: erreur téléchargement PDF : {e}")
            return None

        return self._extract_text(pdf_bytes, pdfplumber)

    def _extract_text(self, pdf_bytes: bytes, pdfplumber) -> str:
        text_parts = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
        except Exception as e:
            raise RuntimeError(f"Extraction texte PDF échouée : {e}") from e
        return "\n".join(text_parts)
