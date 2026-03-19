import csv
import logging
import os
import re
from difflib import SequenceMatcher
from typing import List, Optional, Dict
from django.db.models import Q

logger = logging.getLogger(__name__)


class RidetService:
    """
    Recherche et matching d'établissements dans le référentiel RIDET.

    Deux chemins coexistent intentionnellement :
    - match_company()      → accès DB direct, utilisé par l'API (résultats scorés, pas de cache)
    - get_rid7_by_name()   → cache mémoire, utilisé par les scrapers pour la reconciliation
                             en masse (évite N requêtes DB pendant le scraping)
    """

    CSV_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "sources", "etablissements-actifs-au-ridet.csv"
    )

    IGNORE_NAMES = {
        "sarl", "anonyme", "anonyme ode", "entreprise anonyme",
        "sas", "sa", "nc", "noumea",
    }

    # Cache de classe partagé entre toutes les instances (utilisé par les scrapers)
    _ridet_index: dict = {}
    _official_names: dict = {}
    _loaded: bool = False

    @classmethod
    def match_company(cls, query: str) -> Dict:
        """
        Algorithme de matching intelligent :
        1. Recherche exacte (case-insensitive)
        2. Recherche floue (filtrage SQL + scoring difflib)
        """
        from iod_job_intel.models import RidetEntry

        if not query or len(query.strip()) < 2:
            return {"match_type": "none", "results": []}

        q = query.strip()

        # --- 1. Recherche Exacte ---
        exact_matches = RidetEntry.objects.filter(
            Q(denomination__iexact=q) | Q(enseigne__iexact=q) | Q(sigle__iexact=q)
        )

        count = exact_matches.count()
        if count == 1:
            return {"match_type": "exact_single", "results": cls._serialize_entries(exact_matches)}
        elif count > 1:
            return {"match_type": "exact_multiple", "results": cls._serialize_entries(exact_matches)}

        # --- 2. Recherche Floue ---
        tokens = [t for t in re.findall(r"\w{3,}", q.lower()) if t not in cls.IGNORE_NAMES]
        if not tokens:
            return {"match_type": "none", "results": []}

        filter_query = Q()
        for t in tokens:
            filter_query |= Q(denomination__icontains=t) | Q(enseigne__icontains=t)

        candidates = RidetEntry.objects.filter(filter_query)[:100]

        scored_results = []
        for entry in candidates:
            score = max(
                cls._similarity(q, entry.denomination),
                cls._similarity(q, entry.enseigne),
                cls._similarity(q, entry.sigle),
            )
            if score > 0.3:
                scored_results.append({
                    "rid7": entry.rid7,
                    "denomination": entry.denomination,
                    "enseigne": entry.enseigne,
                    "sigle": entry.sigle,
                    "commune": entry.commune,
                    "forme_juridique": entry.forme_juridique,
                    "score": round(score * 100),
                })

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        final_results = scored_results[:25]

        if not final_results:
            return {"match_type": "none", "results": []}

        return {"match_type": "fuzzy", "results": final_results}

    @staticmethod
    def _similarity(a: Optional[str], b: Optional[str]) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    @staticmethod
    def _serialize_entries(queryset) -> List[Dict]:
        return [
            {
                "rid7": e.rid7,
                "denomination": e.denomination,
                "enseigne": e.enseigne,
                "sigle": e.sigle,
                "commune": e.commune,
                "forme_juridique": e.forme_juridique,
                "score": 100,
            } for e in queryset
        ]

    # ── Cache mémoire (utilisé par les scrapers) ─────────────────────────────────

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
            logger.error(f"[RIDET] Erreur DB lors du chargement du cache : {exc} — fallback CSV")

        cls._load_from_csv()
        cls._loaded = True

    @classmethod
    def _load_from_csv(cls):
        if not os.path.exists(cls.CSV_PATH):
            logger.error(f"[RIDET] CSV manquant : {cls.CSV_PATH}")
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
            logger.error(f"[RIDET] Erreur lecture CSV : {exc}")

    @classmethod
    def _index(cls, name: Optional[str], rid7: str):
        if name:
            k = name.strip().lower()
            if k:
                cls._ridet_index[k] = rid7

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
