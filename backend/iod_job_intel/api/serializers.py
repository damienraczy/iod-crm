from rest_framework import serializers

from iod_job_intel.models import AIAnalysis, AppParameter, JobOffer, RidetEntry, ScrapeLog


class JobOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model  = JobOffer
        fields = [
            "id", "external_id", "source", "title", "company_name", "rid7",
            "contract_type", "location", "experience_req", "education_req",
            "nb_postes", "date_published", "status", "score",
            "description", "url_external", "skills_json", "activities_json",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class JobOfferListSerializer(serializers.ModelSerializer):
    """Serializer allégé pour les listes (sans description longue)."""

    class Meta:
        model  = JobOffer
        fields = [
            "id", "external_id", "source", "title", "company_name", "rid7",
            "contract_type", "location", "date_published", "status", "score",
        ]


class AIAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AIAnalysis
        fields = [
            "id", "job_offer", "rid7", "analysis_type", "model_used",
            "result_text", "result_json", "language", "created_at",
        ]
        read_only_fields = ["id", "created_at", "prompt_hash"]


class RidetEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model  = RidetEntry
        fields = ["rid7", "denomination", "sigle", "enseigne", "commune", "province", "forme_juridique"]


class ScrapeLogSerializer(serializers.ModelSerializer):
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model  = ScrapeLog
        fields = [
            "id", "source", "started_at", "finished_at", "status",
            "offers_imported", "offers_skipped", "error_message", "duration_seconds",
        ]

    def get_duration_seconds(self, obj):
        if obj.finished_at and obj.started_at:
            return round((obj.finished_at - obj.started_at).total_seconds())
        return None


class AppParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AppParameter
        fields = ["key", "value", "description", "updated_at"]
        read_only_fields = ["updated_at"]
