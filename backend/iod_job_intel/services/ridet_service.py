"""
Service de recherche RIDET.

Adapté depuis src/ridet_service.py pour Django ORM.
Maintient un index mémoire de classe pour performances lors du scraping en masse.
Sources par ordre de priorité : table RidetEntry (DB) → fichier CSV (fallback).
"""

import csv
import os
from typing import Optional


class RidetService:
    """Recherche le RID7 d'un établissement dans l'index local."""

    CSV_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "sources", "etablissements-actifs-au-ridet.csv"
    )

    IGNORE_NAMES = {
        "sarl", "anonyme", "anonyme ode", "entreprise anonyme",
        "sas", "sa", "nc", "noumea",
    }

    # Cache de classe partagé entre toutes les instances
    _ridet_index: dict = {}
    _official_names: dict = {}
    _loaded: bool = False

    @classmethod
    def ensure_loaded(cls):
        if not cls._loaded:
            cls._rebuild_index()

    @classmethod
    def invalidate_cache(cls):
        cls._ridet_index = {}
        cls._official_names = {}
        cls._loaded = False

    @classmethod
    def _rebuild_index(cls):
        """Charge l'index depuis la DB (fallback CSV si DB vide)."""
        from iod_job_intel.models import RidetEntry
        try:
            entries = list(RidetEntry.objects.all().values(
                "rid7", "denomination", "enseigne", "sigle"
            ))
            if entries:
                for e in entries:
                    rid7 = e["rid7"]
                    if not rid7:
                        continue
                    display = e["denomination"] or e["enseigne"] or ""
                    cls._official_names[rid7] = display
                    cls._index(e["denomination"], rid7)
                    cls._index(e["enseigne"], rid7)
                    cls._index(e["sigle"], rid7)
                cls._loaded = True
                return
        except Exception as exc:
            print(f"[RIDET] Erreur DB : {exc} — fallback CSV")

        cls._load_from_csv()
        cls._loaded = True

    @classmethod
    def _load_from_csv(cls):
        if not os.path.exists(cls.CSV_PATH):
            print(f"[RIDET] CSV manquant : {cls.CSV_PATH}")
            return
        try:
            with open(cls.CSV_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid7 = row.get("RID7")
                    if not rid7:
                        continue
                    display = row.get("denomination") or row.get("enseigne") or ""
                    cls._official_names[rid7] = display
                    cls._index(row.get("denomination"), rid7)
                    cls._index(row.get("enseigne"), rid7)
                    cls._index(row.get("sigle"), rid7)
        except Exception as exc:
            print(f"[RIDET] Erreur CSV : {exc}")

    @classmethod
    def _index(cls, name: Optional[str], rid7: str):
        if name:
            k = name.strip().lower()
            if k:
                cls._ridet_index[k] = rid7

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_rid7_by_name(self, company_name: str) -> Optional[str]:
        self.ensure_loaded()
        if not company_name:
            return None
        clean = company_name.strip().lower()
        if clean in self.IGNORE_NAMES:
            return None
        return self._ridet_index.get(clean)

    def get_official_name(self, rid7: str) -> str:
        self.ensure_loaded()
        return self._official_names.get(rid7, "Entreprise Inconnue")
