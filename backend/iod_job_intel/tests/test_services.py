"""
Tests des services iod_job_intel.

- AnalysisService : calcul du score, intensité de recrutement
- RidetService    : index mémoire, recherche par nom
- AIService       : prompts (mock Ollama — pas d'appel réseau en test)
"""

from unittest.mock import MagicMock, patch

import pytest

from iod_job_intel.models import JobOffer, RidetEntry, Source
from iod_job_intel.services.analysis_service import AnalysisService
from iod_job_intel.services.ridet_service import RidetService


@pytest.mark.django_db
class TestAnalysisService:
    def setup_method(self):
        self.service = AnalysisService()

    def _offer(self, **kwargs):
        defaults = dict(
            external_id="SC-001", source=Source.GOUV_NC, title="Poste"
        )
        defaults.update(kwargs)
        return JobOffer(**defaults)

    def test_score_zero_by_default(self):
        offer = self._offer()
        assert self.service.calculate_score(offer) == 0

    def test_score_cdi(self):
        offer = self._offer(contract_type="CDI")
        assert self.service.calculate_score(offer) == 20

    def test_score_experience_5ans(self):
        offer = self._offer(experience_req="5 ans expérience requise")
        assert self.service.calculate_score(offer) == 30

    def test_score_experience_2ans(self):
        offer = self._offer(experience_req="2 ans minimum")
        assert self.service.calculate_score(offer) == 15

    def test_score_education_bac5(self):
        offer = self._offer(education_req="Bac +5 ou master")
        assert self.service.calculate_score(offer) == 20

    def test_score_education_bac3(self):
        offer = self._offer(education_req="Bac +3 licence")
        assert self.service.calculate_score(offer) == 10

    def test_score_multi_postes(self):
        offer = self._offer(nb_postes=3)
        assert self.service.calculate_score(offer) == 10

    def test_score_capped_at_100(self):
        offer = self._offer(
            contract_type="CDI",
            experience_req="10 ans",
            education_req="master",
            nb_postes=5,
        )
        score = self.service.calculate_score(offer)
        assert score <= 100

    def test_score_full_combination(self):
        offer = self._offer(
            contract_type="CDI",
            experience_req="5 ans expérience",
            education_req="Bac +5",
            nb_postes=2,
        )
        assert self.service.calculate_score(offer) == min(20 + 30 + 20 + 10, 100)

    @pytest.mark.django_db
    def test_recruitment_intensity_no_offers(self):
        result = self.service.get_company_recruitment_intensity("9999999")
        assert result["total_offers"] == 0
        assert result["distinct_roles"] == 0
        assert result["is_growing"] is False

    @pytest.mark.django_db
    def test_recruitment_intensity_growing(self):
        rid7 = "1234567"
        for i in range(6):
            JobOffer.objects.create(
                external_id=f"G-{i:03d}",
                source=Source.GOUV_NC,
                title=f"Poste {i}",
                rid7=rid7,
            )
        result = self.service.get_company_recruitment_intensity(rid7)
        assert result["total_offers"] == 6
        assert result["is_growing"] is True


@pytest.mark.django_db
class TestRidetService:
    def setup_method(self):
        RidetService.invalidate_cache()

    def teardown_method(self):
        RidetService.invalidate_cache()

    def test_lookup_by_denomination(self):
        RidetEntry.objects.create(
            rid7="1234567", denomination="AIR CALEDONIE"
        )
        svc  = RidetService()
        rid7 = svc.get_rid7_by_name("AIR CALEDONIE")
        assert rid7 == "1234567"

    def test_lookup_case_insensitive(self):
        RidetEntry.objects.create(
            rid7="2345678", denomination="ENERCAL"
        )
        svc = RidetService()
        assert svc.get_rid7_by_name("enercal") == "2345678"
        assert svc.get_rid7_by_name("Enercal") == "2345678"

    def test_lookup_by_enseigne(self):
        RidetEntry.objects.create(
            rid7="3456789", denomination="SOCIETE X SA",
            enseigne="SUPER MARCHÉ X"
        )
        svc = RidetService()
        assert svc.get_rid7_by_name("SUPER MARCHÉ X") == "3456789"

    def test_lookup_unknown_returns_none(self):
        svc = RidetService()
        assert svc.get_rid7_by_name("Entreprise Inconnue XYZ") is None

    def test_ignore_generic_names(self):
        svc = RidetService()
        for name in ["SARL", "Anonyme", "SAS", "SA", "NC"]:
            assert svc.get_rid7_by_name(name) is None

    def test_none_input(self):
        svc = RidetService()
        assert svc.get_rid7_by_name(None) is None
        assert svc.get_rid7_by_name("") is None

    def test_get_official_name(self):
        RidetEntry.objects.create(
            rid7="4567890", denomination="OFFICE DES POSTES"
        )
        svc = RidetService()
        assert svc.get_official_name("4567890") == "OFFICE DES POSTES"

    def test_get_official_name_unknown(self):
        svc = RidetService()
        assert svc.get_official_name("0000000") == "Entreprise Inconnue"

    def test_invalidate_cache(self):
        """Après invalidation, le cache se recharge depuis la DB."""
        RidetEntry.objects.create(rid7="5678901", denomination="KARUÏA")
        svc = RidetService()
        assert svc.get_rid7_by_name("KARUÏA") == "5678901"

        RidetService.invalidate_cache()
        RidetEntry.objects.create(rid7="6789012", denomination="OPT NC")
        svc2 = RidetService()
        assert svc2.get_rid7_by_name("OPT NC") == "6789012"


class TestAIServicePrompts:
    """Tests AIService sans appel réseau — mock de _post_with_retry."""

    def _make_service(self):
        from iod_job_intel.services.ai_service import AIService
        return AIService(model="test-model")

    @patch("iod_job_intel.services.ai_service.requests.post")
    def test_analyze_offer_valid(self, mock_post):
        """analyze_offer retourne critical_skills si la réponse est valide."""
        import json
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": json.dumps({
                "critical_skills": [
                    {"skill": "Python", "reason": "hard to assess", "sales_hook": "hook"}
                ]
            })
        }
        mock_post.return_value = mock_resp

        svc = self._make_service()
        # Fournir le prompt directement via fichier fallback
        with patch.object(svc, "_read_prompt", return_value="Analyze {title} {experience} {skills} {language}"):
            result = svc.analyze_offer("DRH", "5 ans", "management", "French")

        assert "critical_skills" in result
        assert len(result["critical_skills"]) == 1

    @patch("iod_job_intel.services.ai_service.requests.post")
    def test_generate_email_returns_text(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Bonjour Madame,\n\nEmail de test."}
        mock_post.return_value = mock_resp

        svc = self._make_service()
        with patch.object(svc, "_read_prompt", return_value="Email {title} {source} {contact_name} {questions_brulantes} {language}"):
            result = svc.generate_email("Dev", "job.nc", "M. Dupont", "q1\nq2", "French")

        assert "Bonjour" in result

    @patch("iod_job_intel.services.ai_service.requests.post")
    def test_retry_on_network_error(self, mock_post):
        """_post_with_retry réessaie en cas d'erreur réseau."""
        import requests as req_lib
        from unittest.mock import MagicMock

        mock_ok = MagicMock()
        mock_ok.json.return_value = {"response": "ok"}
        mock_post.side_effect = [
            req_lib.exceptions.ConnectionError("connexion refusée"),
            mock_ok,
        ]

        svc = self._make_service()
        with patch("iod_job_intel.services.ai_service.time.sleep"):
            resp = svc._post_with_retry({"model": "test", "prompt": "test"}, max_retries=2)
        assert resp == mock_ok
        assert mock_post.call_count == 2
