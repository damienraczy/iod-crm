"""
Tests des modèles iod_job_intel.

Couvre : création, déduplication, AppParameter.get(), ScrapeLog.finalize().
"""

import pytest
from django.utils import timezone

from iod_job_intel.models import (
    AIAnalysis,
    AIAnalysisType,
    AppParameter,
    JobOffer,
    JobOfferStatus,
    PromptTemplate,
    RidetEntry,
    ScrapeLog,
    ScrapeStatus,
    Source,
)


@pytest.mark.django_db
class TestJobOffer:
    def test_create_minimal(self):
        offer = JobOffer.objects.create(
            external_id="TEST-001",
            source=Source.GOUV_NC,
            title="Développeur Python",
            company_name="IOD Ingénierie",
        )
        assert offer.pk is not None
        assert offer.status == JobOfferStatus.NEW
        assert offer.score == 0

    def test_deduplication_by_external_id(self):
        """Deux offres avec le même external_id + source sont refusées."""
        JobOffer.objects.create(
            external_id="DUP-001", source=Source.PSUD, title="Comptable"
        )
        with pytest.raises(Exception):
            JobOffer.objects.create(
                external_id="DUP-001", source=Source.PSUD, title="Comptable bis"
            )

    def test_same_external_id_different_source(self):
        """Le même external_id sur deux sources différentes est valide."""
        JobOffer.objects.create(
            external_id="SHARED-001", source=Source.GOUV_NC, title="Poste A"
        )
        offer2 = JobOffer.objects.create(
            external_id="SHARED-001", source=Source.JOB_NC, title="Poste B"
        )
        assert offer2.pk is not None

    def test_rid7_index(self):
        """Filtrage par rid7 doit fonctionner."""
        JobOffer.objects.create(
            external_id="R-001", source=Source.GOUV_NC,
            title="DRH", rid7="1234567", company_name="Acme"
        )
        JobOffer.objects.create(
            external_id="R-002", source=Source.GOUV_NC,
            title="RRH", rid7="1234567", company_name="Acme"
        )
        JobOffer.objects.create(
            external_id="R-003", source=Source.GOUV_NC,
            title="Chef", rid7="9999999", company_name="Other"
        )
        assert JobOffer.objects.filter(rid7="1234567").count() == 2

    def test_skills_json_stored_as_list(self):
        offer = JobOffer.objects.create(
            external_id="SK-001", source=Source.JOB_NC,
            title="Dev", skills_json=["Python", "Django"]
        )
        reloaded = JobOffer.objects.get(pk=offer.pk)
        assert reloaded.skills_json == ["Python", "Django"]

    def test_str_representation(self):
        offer = JobOffer(
            source=Source.PSUD, title="Manager", company_name="Test SARL"
        )
        assert "PSUD" in str(offer)
        assert "Manager" in str(offer)


@pytest.mark.django_db
class TestRidetEntry:
    def test_create(self):
        entry = RidetEntry.objects.create(
            rid7="1234567",
            denomination="AIR CALEDONIE",
            commune="Nouméa",
            province="Province Sud",
        )
        assert entry.rid7 == "1234567"

    def test_unique_rid7(self):
        RidetEntry.objects.create(rid7="7654321", denomination="ENERCAL")
        with pytest.raises(Exception):
            RidetEntry.objects.create(rid7="7654321", denomination="ENERCAL 2")


@pytest.mark.django_db
class TestAppParameter:
    def test_get_existing(self):
        AppParameter.objects.create(key="ai.model", value="qwen3:latest")
        assert AppParameter.get("ai.model") == "qwen3:latest"

    def test_get_missing_returns_default(self):
        assert AppParameter.get("does.not.exist", "fallback") == "fallback"
        assert AppParameter.get("does.not.exist") is None

    def test_get_int(self):
        AppParameter.objects.create(key="limit", value="42")
        assert AppParameter.get_int("limit") == 42

    def test_get_int_invalid_returns_default(self):
        AppParameter.objects.create(key="bad.int", value="notanumber")
        assert AppParameter.get_int("bad.int", default=99) == 99


@pytest.mark.django_db
class TestScrapeLog:
    def test_finalize_success(self):
        log = ScrapeLog.objects.create(source=Source.GOUV_NC)
        assert log.status == ScrapeStatus.RUNNING

        log.finalize(imported=10, skipped=3)
        assert log.status == ScrapeStatus.SUCCESS
        assert log.offers_imported == 10
        assert log.offers_skipped == 3
        assert log.finished_at is not None
        assert log.error_message == ""

    def test_finalize_with_error(self):
        log = ScrapeLog.objects.create(source=Source.JOB_NC)
        log.finalize(imported=0, skipped=0, error="Timeout réseau")
        assert log.status == ScrapeStatus.FAILED
        assert log.error_message == "Timeout réseau"


@pytest.mark.django_db
class TestAIAnalysis:
    def test_create_linked_to_offer(self):
        offer = JobOffer.objects.create(
            external_id="AI-001", source=Source.GOUV_NC, title="CTO"
        )
        analysis = AIAnalysis.objects.create(
            job_offer=offer,
            analysis_type=AIAnalysisType.OFFER_DIAGNOSTIC,
            model_used="llama3.2",
            prompt_hash="abc123" * 10 + "abcd",
            result_text="Diagnostic OK",
        )
        assert analysis.job_offer == offer
        assert offer.ai_analyses.count() == 1

    def test_create_linked_to_rid7(self):
        analysis = AIAnalysis.objects.create(
            rid7="1234567",
            analysis_type=AIAnalysisType.QUESTIONS_COMPANY,
            model_used="qwen3",
            prompt_hash="x" * 64,
            result_text="Questions...",
        )
        assert analysis.job_offer is None
        assert analysis.rid7 == "1234567"


@pytest.mark.django_db
class TestPromptTemplate:
    def test_create_and_retrieve(self):
        PromptTemplate.objects.create(
            name="skill_analysis",
            template="Analyse {title}...",
            is_system=False,
        )
        pt = PromptTemplate.objects.get(name="skill_analysis")
        assert "{title}" in pt.template
        assert pt.is_system is False

    def test_system_prompt(self):
        PromptTemplate.objects.create(
            name="system_R6",
            template="You are...",
            is_system=True,
        )
        assert PromptTemplate.objects.filter(is_system=True).count() == 1
