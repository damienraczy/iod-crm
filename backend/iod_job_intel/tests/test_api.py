"""
Tests des endpoints API iod_job_intel.

Utilise admin_client (fixture conftest.py) qui fournit un token JWT valide.
"""

import pytest

from iod_job_intel.models import AppParameter, JobOffer, RidetEntry, ScrapeLog, Source


@pytest.mark.django_db
class TestJobOfferAPI:
    BASE = "/api/iod/offers/"

    def test_list_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get(self.BASE)
        assert response.status_code in (401, 403)

    def test_list_empty(self, admin_client):
        response = admin_client.get(self.BASE)
        assert response.status_code == 200

    def test_list_returns_offers(self, admin_client):
        JobOffer.objects.create(
            external_id="API-001", source=Source.GOUV_NC,
            title="Comptable", company_name="Acme"
        )
        response = admin_client.get(self.BASE)
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

    def test_filter_by_rid7(self, admin_client):
        JobOffer.objects.create(
            external_id="R7-001", source=Source.GOUV_NC,
            title="DRH", rid7="1234567", company_name="Acme"
        )
        JobOffer.objects.create(
            external_id="R7-002", source=Source.GOUV_NC,
            title="Chef", rid7="9999999", company_name="Other"
        )
        response = admin_client.get(f"{self.BASE}?rid7=1234567")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["rid7"] == "1234567"

    def test_filter_by_source(self, admin_client):
        JobOffer.objects.create(
            external_id="SRC-001", source=Source.PSUD, title="Dev"
        )
        JobOffer.objects.create(
            external_id="SRC-002", source=Source.JOB_NC, title="Compta"
        )
        response = admin_client.get(f"{self.BASE}?source=PSUD")
        assert response.status_code == 200
        data = response.json()
        assert all(r["source"] == "PSUD" for r in data["results"])

    def test_filter_by_q(self, admin_client):
        JobOffer.objects.create(
            external_id="Q-001", source=Source.GOUV_NC,
            title="Développeur Python", company_name="TechNC"
        )
        JobOffer.objects.create(
            external_id="Q-002", source=Source.GOUV_NC,
            title="Comptable", company_name="FinanceNC"
        )
        response = admin_client.get(f"{self.BASE}?q=python")
        data = response.json()
        assert data["count"] == 1
        assert "Python" in data["results"][0]["title"]

    def test_detail_view(self, admin_client):
        offer = JobOffer.objects.create(
            external_id="DET-001", source=Source.GOUV_NC,
            title="Manager", description="Description complète"
        )
        response = admin_client.get(f"{self.BASE}{offer.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Manager"
        assert "description" in data

    def test_detail_includes_description(self, admin_client):
        """Le sérialiseur de détail inclut description, le list ne l'inclut pas."""
        offer = JobOffer.objects.create(
            external_id="DESC-001", source=Source.GOUV_NC,
            title="Chef projet", description="Texte long..."
        )
        list_resp   = admin_client.get(self.BASE)
        detail_resp = admin_client.get(f"{self.BASE}{offer.pk}/")

        list_keys   = list_resp.json()["results"][0].keys()
        detail_keys = detail_resp.json().keys()

        assert "description" not in list_keys
        assert "description" in detail_keys

    def test_analyses_subresource(self, admin_client):
        from iod_job_intel.models import AIAnalysis, AIAnalysisType
        offer = JobOffer.objects.create(
            external_id="AN-001", source=Source.GOUV_NC, title="CTO"
        )
        AIAnalysis.objects.create(
            job_offer=offer,
            analysis_type=AIAnalysisType.OFFER_DIAGNOSTIC,
            model_used="llama3.2",
            prompt_hash="a" * 64,
            result_text="Diagnostic...",
        )
        response = admin_client.get(f"{self.BASE}{offer.pk}/analyses/")
        assert response.status_code == 200
        assert len(response.json()) == 1


@pytest.mark.django_db
class TestRidetSearchAPI:
    URL = "/api/iod/ridet/search/"

    def test_requires_auth(self, unauthenticated_client):
        response = unauthenticated_client.get(f"{self.URL}?q=air")
        assert response.status_code in (401, 403)

    def test_missing_q_returns_400(self, admin_client):
        response = admin_client.get(self.URL)
        assert response.status_code == 400

    def test_short_q_returns_400(self, admin_client):
        response = admin_client.get(f"{self.URL}?q=a")
        assert response.status_code == 400

    def test_search_returns_results(self, admin_client):
        RidetEntry.objects.create(rid7="1234567", denomination="AIR CALEDONIE")
        response = admin_client.get(f"{self.URL}?q=air")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["rid7"] == "1234567"

    def test_search_no_results(self, admin_client):
        response = admin_client.get(f"{self.URL}?q=xyzimpossible")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.django_db
class TestScrapeLogAPI:
    URL = "/api/iod/logs/"

    def test_list_logs(self, admin_client):
        ScrapeLog.objects.create(source=Source.GOUV_NC)
        response = admin_client.get(self.URL)
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_filter_by_source(self, admin_client):
        ScrapeLog.objects.create(source=Source.PSUD)
        ScrapeLog.objects.create(source=Source.JOB_NC)
        response = admin_client.get(f"{self.URL}?source=PSUD")
        data = response.json()
        assert all(r["source"] == "PSUD" for r in data["results"])


@pytest.mark.django_db
class TestAppParameterAPI:
    URL = "/api/iod/parameters/"

    def test_list_parameters(self, admin_client):
        AppParameter.objects.create(key="ai.model", value="llama3.2")
        response = admin_client.get(self.URL)
        assert response.status_code == 200

    def test_retrieve_by_key(self, admin_client):
        AppParameter.objects.create(
            key="ai.timeout", value="60", description="Timeout Ollama"
        )
        response = admin_client.get(f"{self.URL}ai.timeout/")
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "60"

    def test_update_value(self, admin_client):
        AppParameter.objects.create(key="scraper.limit", value="10")
        response = admin_client.patch(
            f"{self.URL}scraper.limit/", {"value": "25"}, format="json"
        )
        assert response.status_code == 200
        assert AppParameter.objects.get(key="scraper.limit").value == "25"
