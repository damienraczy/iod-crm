from django.contrib import admin
from django.utils.html import format_html

from .models import AIAnalysis, AppParameter, JobOffer, JobSource, PromptTemplate, RidetEntry, ScrapeLog


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display  = ("title", "company_name", "source", "status", "score", "date_published", "rid7")
    list_filter   = ("source", "status", "contract_type")
    search_fields = ("title", "company_name", "rid7", "external_id")
    readonly_fields = ("external_id", "created_at", "updated_at")
    ordering      = ("-date_published",)
    list_per_page = 50

    fieldsets = (
        ("Identification", {
            "fields": ("external_id", "source", "status", "score")
        }),
        ("Contenu", {
            "fields": ("title", "description", "raw_description", "rome_code",
                       "contract_type", "location", "experience_req",
                       "education_req", "qualification", "nb_postes", "url_external")
        }),
        ("Données structurées", {
            "fields": ("skills_json", "activities_json"),
            "classes": ("collapse",),
        }),
        ("Liaison CRM", {
            "fields": ("rid7", "company_name")
        }),
        ("Dates", {
            "fields": ("date_published", "created_at", "updated_at")
        }),
    )


@admin.register(RidetEntry)
class RidetEntryAdmin(admin.ModelAdmin):
    list_display  = ("rid7", "denomination", "enseigne", "commune", "province", "forme_juridique")
    search_fields = ("rid7", "denomination", "enseigne", "sigle")
    list_filter   = ("province", "commune")
    ordering      = ("rid7",)
    list_per_page = 100


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display  = ("analysis_type", "job_offer", "rid7", "model_used", "language", "created_at")
    list_filter   = ("analysis_type", "language", "model_used")
    search_fields = ("rid7", "job_offer__title", "result_text")
    readonly_fields = ("prompt_hash", "created_at")
    ordering      = ("-created_at",)


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display  = ("name", "description", "is_system", "version", "updated_at")
    search_fields = ("name", "description")
    list_filter   = ("is_system",)
    readonly_fields = ("updated_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ("name",)
        return self.readonly_fields


@admin.register(ScrapeLog)
class ScrapeLogAdmin(admin.ModelAdmin):
    list_display  = ("source", "started_at", "finished_at", "status",
                     "offers_imported", "offers_skipped", "has_error")
    list_filter   = ("source", "status")
    readonly_fields = ("started_at", "finished_at", "offers_imported",
                       "offers_skipped", "error_message", "status")
    ordering      = ("-started_at",)

    @admin.display(boolean=True, description="Erreur")
    def has_error(self, obj):
        return bool(obj.error_message)


@admin.register(AppParameter)
class AppParameterAdmin(admin.ModelAdmin):
    list_display  = ("key", "value", "description", "updated_at")
    search_fields = ("key", "description")
    readonly_fields = ("updated_at",)


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display  = ("label", "code", "url", "is_active")
    list_editable = ("is_active",)
    search_fields = ("code", "label")
    ordering      = ("label",)

    def has_module_perms(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
