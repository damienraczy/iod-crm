"""
Service d'intelligence artificielle — wrapper Ollama.

Adapté depuis src/ai_service.py (app Qt) pour Django :
- Connexion cloud prioritaire : OLLAMA_CLOUD_URL + OLLAMA_API_KEY dans .env
- Fallback local : OLLAMA_CLOUD_URL (défaut localhost:11434), sans auth
- Prompts chargés depuis PromptTemplate en DB (fallback sur fichiers .txt dans prompts/)
- Cache des résultats via AIAnalysis.prompt_hash (SHA-256)
"""

import hashlib
import json
import os
import re
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings


def _require_model(key: str) -> str:
    """
    Lit le modèle depuis AppParameter 'ai.model.<key>'.
    Lève RuntimeError si absent — aucun fallback.
    """
    from iod_job_intel.models import AppParameter
    value = AppParameter.get(f"ai.model.{key}")
    if not value:
        raise RuntimeError(
            f"AppParameter 'ai.model.{key}' manquant. "
            f"L'ajouter dans la page Paramètres du module."
        )
    return value


def _get_timeout() -> int:
    """Timeout en secondes — AppParameter 'ai.timeout' prioritaire sur OLLAMA_TIMEOUT."""
    from iod_job_intel.models import AppParameter
    val = AppParameter.get("ai.timeout")
    if val:
        return int(val)
    return getattr(settings, "OLLAMA_TIMEOUT", 300)


class AIService:
    """Interagit avec Ollama cloud pour l'analyse des offres d'emploi."""

    PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

    def __init__(self, model: Optional[str] = None):
        """
        model : override explicite (ex: tests). Si None, utilise ai.model.general.
        Lève RuntimeError si OLLAMA_CLOUD_URL ou OLLAMA_API_KEY manquent.
        """
        cloud_url = getattr(settings, "OLLAMA_CLOUD_URL", "")
        api_key   = getattr(settings, "OLLAMA_API_KEY", "")

        if not cloud_url:
            raise RuntimeError("OLLAMA_CLOUD_URL manquant — vérifier .env.docker")
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY manquant — vérifier .env.docker")

        self.base_url      = cloud_url
        self._api_key      = api_key
        self._model_override = model  # None = lire depuis AppParameter à chaque appel

    def _current_model(self) -> str:
        if self._model_override:
            return self._model_override
        return _require_model("general")

    def _read_prompt(self, name: str) -> str:
        """Charge un template depuis PromptTemplate (DB) ou fichier .txt (fallback)."""
        from iod_job_intel.models import PromptTemplate

        try:
            return PromptTemplate.objects.get(name=name).template
        except PromptTemplate.DoesNotExist:
            pass

        # Fallback fichier
        path = os.path.join(self.PROMPT_DIR, f"{name}.txt")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Prompt '{name}' introuvable en DB et absent de {path}"
            )
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _post_with_retry(
        self, payload: Dict[str, Any], max_retries: int = 1
    ) -> requests.Response:
        """POST vers Ollama cloud — pas de retry (erreurs doivent remonter immédiatement)."""
        headers = {"Authorization": f"Bearer {self._api_key}"}

        response = requests.post(
            self.base_url, json=payload, headers=headers,
            timeout=_get_timeout(), allow_redirects=False
        )

        # Exposer les détails bruts si la réponse n'est pas 2xx
        if not response.ok:
            location = response.headers.get("Location", "—")
            raise RuntimeError(
                f"Ollama cloud HTTP {response.status_code} "
                f"sur {response.url} | "
                f"Location: {location} | "
                f"Body: {response.text[:300]}"
            )

        return response

    @staticmethod
    def _hash_prompt(prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def analyze_offer(
        self, title: str, experience: str, skills_list: str, language: str = "French"
    ) -> Dict[str, Any]:
        """Identifie les 3 compétences critiques d'une offre (réponse JSON)."""
        template = self._read_prompt("skill_analysis")
        prompt = template.format(
            title=title,
            experience=experience or "Not specified",
            skills=skills_list or "Not provided",
            language=language,
        )
        payload = {
            "model": self._current_model(),
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            response = self._post_with_retry(payload)
            raw = response.json().get("response", "")
            data = json.loads(raw)
            if "critical_skills" not in data:
                raise ValueError("LLM response missing 'critical_skills' key")
            return data
        except Exception as e:
            raise RuntimeError(f"analyze_offer échoué : {e}") from e

    def diagnose_offer(
        self,
        title: str,
        location: str,
        description: str,
        experience: str,
        education: str,
        language: str = "French",
    ) -> str:
        """Génère un diagnostic qualitatif de l'offre d'emploi."""
        template = self._read_prompt("offer_diagnostic")
        prompt = template.format(
            title=title,
            location=location or "N/C",
            description=description or "No description provided",
            experience=experience or "Not specified",
            education=education or "Not specified",
            language=language,
        )
        payload = {"model": self._current_model(), "prompt": prompt, "stream": False}
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"diagnose_offer échoué : {e}") from e

    def generate_questions_brulantes_offre(
        self,
        title: str,
        education: str,
        description: str,
        skills: str,
        activities: str,
        company_context: str = "",
        language: str = "English",
    ) -> str:
        """Questions brûlantes sur les compétences requises par l'offre."""
        system_prompt = self._read_prompt("system_R6_I6_skills")
        template = self._read_prompt("questions_brulantes_offre")
        prompt = template.format(
            title=title or "Not specified",
            education=education or "Not specified",
            description=description or "Not provided",
            skills=skills or "Not provided",
            activities=activities or "Not provided",
            company_context=company_context or "Not provided",
            language=language,
        )
        payload = {
            "model": self._current_model(),
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(
                f"generate_questions_brulantes_offre échoué : {e}"
            ) from e

    def generate_questions_brulantes(
        self, title: str, description: str, company_context: str, language: str
    ) -> str:
        """Questions brûlantes sur les capacités organisationnelles de l'entreprise."""
        system_prompt = self._read_prompt("system_R6_O6_capacities")
        template = self._read_prompt("questions_brulantes_company")
        prompt = template.format(
            title=title or "Not specified",
            description=description or "Not provided",
            company_context=company_context or "Not provided",
            language=language,
        )
        payload = {
            "model": self._current_model(),
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
        }
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"generate_questions_brulantes échoué : {e}") from e

    def generate_email(
        self,
        title: str,
        source: str,
        contact_name: str,
        questions_brulantes: str,
        language: str,
    ) -> str:
        """Génère un email de prospection lié à une offre d'emploi spécifique."""
        template = self._read_prompt("email_prospect_job")
        prompt = template.format(
            title=title or "Non précisé",
            source=source or "Non précisé",
            contact_name=contact_name or "Madame, Monsieur",
            questions_brulantes=questions_brulantes or "Non renseignées",
            language=language,
        )
        payload = {"model": self._current_model(), "prompt": prompt, "stream": False}
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"generate_email échoué : {e}") from e

    def generate_email_general(
        self,
        company_name: str,
        contact_name: str,
        questions_brulantes: str,
        language: str,
    ) -> str:
        """Génère un email de prospection général (sans offre spécifique)."""
        template = self._read_prompt("email_prospect_general")
        prompt = template.format(
            company_name=company_name or "votre entreprise",
            contact_name=contact_name or "Madame, Monsieur",
            questions_brulantes=questions_brulantes,
            language=language,
        )
        payload = {"model": self._current_model(), "prompt": prompt, "stream": False}
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"generate_email_general échoué : {e}") from e

    def classify_offer(self, title: str, description: str, qualification: str = "", experience: str = "") -> str:
        """
        Classifie une offre d'emploi en eval_n4…eval_n8.
        Utilise ai.model.classifier avec temperature=0.0.
        Retourne le code (ex: 'eval_n5') ou lève RuntimeError.
        """
        valid_codes = {"eval_n4", "eval_n5", "eval_n6", "eval_n7", "eval_n8"}
        model = _require_model("classifier")

        context_parts = [f"Intitulé : {title}"]
        if qualification:
            context_parts.append(f"Qualification requise : {qualification}")
        if experience:
            context_parts.append(f"Expérience requise : {experience}")
        if description:
            context_parts.append(f"Description (extrait) : {description[:800]}")
        context = "\n".join(context_parts)

        template = self._read_prompt("classify_offer")
        prompt = template.format(context=context)

        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }

        try:
            response = requests.post(
                self.base_url, json=payload, headers=headers,
                timeout=30, allow_redirects=False
            )
            if not response.ok:
                raise RuntimeError(
                    f"Ollama HTTP {response.status_code} : {response.text[:200]}"
                )
            raw = response.json().get("response", "")
            if isinstance(raw, dict):
                data = raw
            else:
                # Le modèle peut envelopper le JSON dans du markdown (```json ... ```)
                # On extrait le premier objet JSON trouvé dans la réponse
                match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
                if not match:
                    raise ValueError(f"Aucun JSON trouvé dans la réponse : {raw[:200]!r}")
                data = json.loads(match.group(0))
            code = data.get("code", "").strip()
            if code not in valid_codes:
                raise ValueError(f"Code inattendu du LLM : {code!r}")
            return code
        except Exception as e:
            raise RuntimeError(f"classify_offer échoué : {e}") from e

    def extract_ridet_pdf(self, pdf_text: str) -> dict:
        """
        Extrait les données structurées d'un texte issu d'un PDF Avis RIDET.
        Retourne un dict avec les clés 'entreprise' et 'etablissement'.
        Utilise le modèle classificateur (plus rapide, temperature=0.0).
        """
        template = self._read_prompt("extract_ridet_pdf")
        prompt = template.format(pdf_text=pdf_text[:6000])

        payload = {
            "model": _require_model("classifier"),
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        try:
            response = self._post_with_retry(payload)
            raw = response.json().get("response", "")
            if isinstance(raw, dict):
                return raw
            # Extraire le premier JSON imbriqué (peut être enveloppé en markdown)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                raise ValueError(f"Aucun JSON dans la réponse : {raw[:200]!r}")
            return json.loads(match.group(0))
        except Exception as e:
            raise RuntimeError(f"extract_ridet_pdf échoué : {e}") from e

    def generate_ice_breaker(
        self, company_name: str, job_title: str, language: str = "French"
    ) -> str:
        """Génère une phrase d'accroche personnalisée pour un email commercial."""
        template = self._read_prompt("ice_breaker")
        prompt = template.format(
            company_name=company_name,
            job_title=job_title,
            language=language,
        )
        payload = {"model": self._current_model(), "prompt": prompt, "stream": False}
        try:
            response = self._post_with_retry(payload)
            return response.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"generate_ice_breaker échoué : {e}") from e
