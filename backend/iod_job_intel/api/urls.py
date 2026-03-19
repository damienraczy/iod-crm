from django.urls import include, path
from rest_framework.routers import DefaultRouter

from iod_job_intel.api.views import (
    AIAnalysisViewSet,
    AppParameterViewSet,
    CompanyAIView,
    JobOfferViewSet,
    RidetCRMAccountView,
    RidetConsolidateView,
    RidetDetailView,
    RidetRefreshView,
    RidetMatchView,
    RidetSearchView,
    ScrapeLogViewSet,
    SyncTriggerView,
)

router = DefaultRouter()
router.register(r"offers",     JobOfferViewSet,     basename="joboffer")
router.register(r"analyses",   AIAnalysisViewSet,   basename="aianalysis")
router.register(r"logs",       ScrapeLogViewSet,    basename="scrapelog")
router.register(r"parameters", AppParameterViewSet, basename="appparameter")

urlpatterns = [
    path("", include(router.urls)),
    path("ridet/search/",                              RidetSearchView.as_view(),      name="ridet-search"),
    path("ridet/match/",                               RidetMatchView.as_view(),       name="ridet-match"),
    path("ridet/refresh/",                             RidetRefreshView.as_view(),     name="ridet-refresh"),
    path("ridet/<str:rid7>/",                          RidetDetailView.as_view(),      name="ridet-detail"),
    path("ridet/<str:rid7>/consolidate/",              RidetConsolidateView.as_view(), name="ridet-consolidate"),
    path("ridet/<str:rid7>/crm-account/",              RidetCRMAccountView.as_view(),  name="ridet-crm-account"),
    path("ridet/<str:rid7>/ai/<str:ai_action>/",       CompanyAIView.as_view(),        name="company-ai"),
    path("sync/trigger/",                              SyncTriggerView.as_view(),  name="sync-trigger"),
]
