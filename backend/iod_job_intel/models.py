"""
Modèles de données pour l'app iod_job_intel.

Tables :
- JobOffer      : offres d'emploi scrapées depuis les sources NC
- RidetEntry    : référentiel officiel des établissements (RIDET)
- AIAnalysis    : résultats des analyses LLM (par offre ou par rid7)
- PromptTemplate: templates de prompts Ollama gérés en base
- ScrapeLog     : journal de chaque session de scraping
- AppParameter  : configuration dynamique clé/valeur

Liaison avec django-crm : uniquement via le champ rid7 (clé naturelle NC).
Aucune ForeignKey vers les modèles de django-crm.
"""

from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

class Source(models.TextChoices):
    GOUV_NC    = "GOUV_NC",    "Emploi Gouv NC"
    PSUD       = "PSUD",       "Province Sud"
    JOB_NC     = "JOB_NC",     "Job.nc"
    LEMPLOI_NC = "LEMPLOI_NC", "L'Emploi.nc"


class JobOfferStatus(models.TextChoices):
    NEW      = "NEW",      "Nouvelle"
    PUBLIEE  = "PUBLIEE",  "Publiée"
    ARCHIVEE = "ARCHIVEE", "Archivée"


class ScrapeStatus(models.TextChoices):
    RUNNING = "RUNNING", "En cours"
    SUCCESS = "SUCCESS", "Succès"
    PARTIAL = "PARTIAL", "Partiel"
    FAILED  = "FAILED",  "Échoué"


class AIAnalysisType(models.TextChoices):
    SKILL_ANALYSIS    = "skill_analysis",    "Analyse compétences"
    OFFER_DIAGNOSTIC  = "offer_diagnostic",  "Diagnostic offre"
    QUESTIONS_OFFRE   = "questions_offre",   "Questions brûlantes (offre)"
    QUESTIONS_COMPANY = "questions_company", "Questions brûlantes (entreprise)"
    EMAIL_JOB         = "email_job",         "Email prospection (offre)"
    EMAIL_GENERAL     = "email_general",     "Email prospection (général)"
    ICE_BREAKER       = "ice_breaker",       "Ice breaker"


# ---------------------------------------------------------------------------
# JobOffer
# ---------------------------------------------------------------------------

class JobOffer(models.Model):
    """Offre d'emploi importée depuis une source externe (API ou scraping)."""

    # Identification
    external_id   = models.CharField(max_length=100, db_index=True)
    source        = models.CharField(max_length=20, choices=Source.choices)

    # Contenu
    title         = models.CharField(max_length=255)
    description   = models.TextField(blank=True)
    raw_description = models.TextField(blank=True)
    rome_code     = models.CharField(max_length=10, blank=True)
    contract_type = models.CharField(max_length=50, blank=True)
    location      = models.CharField(max_length=100, blank=True)
    experience_req = models.CharField(max_length=100, blank=True)
    education_req = models.TextField(blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    nb_postes     = models.PositiveSmallIntegerField(default=1)
    url_external  = models.URLField(max_length=500, blank=True)

    # Données structurées
    skills_json     = models.JSONField(default=list, blank=True)
    activities_json = models.JSONField(default=list, blank=True)

    # Dates
    date_published = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # Statut et score de priorité
    status = models.CharField(
        max_length=50, choices=JobOfferStatus.choices, default=JobOfferStatus.NEW
    )
    score = models.PositiveSmallIntegerField(default=0)

    # Pivot vers django-crm (liaison faible — pas de FK)
    rid7         = models.CharField(max_length=20, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date_published"]
        unique_together = [("external_id", "source")]
        indexes = [
            models.Index(fields=["source", "external_id"]),
            models.Index(fields=["rid7"]),
            models.Index(fields=["status", "score"]),
        ]
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"

    def __str__(self):
        return f"[{self.source}] {self.title} — {self.company_name}"


# ---------------------------------------------------------------------------
# RidetEntry
# ---------------------------------------------------------------------------

class RidetEntry(models.Model):
    """Entrée du registre officiel RIDET des établissements actifs en NC."""

    rid7              = models.CharField(max_length=20, unique=True, db_index=True)
    denomination      = models.CharField(max_length=255, blank=True, db_index=True)
    sigle             = models.CharField(max_length=100, blank=True)
    enseigne          = models.CharField(max_length=255, blank=True, db_index=True)
    date_etablissement = models.DateField(null=True, blank=True)
    commune           = models.CharField(max_length=100, blank=True)
    province          = models.CharField(max_length=100, blank=True)
    forme_juridique   = models.CharField(max_length=100, blank=True)
    
    # Champs consolidés via Infogreffe.nc
    adresse            = models.TextField(blank=True)
    code_naf           = models.CharField(max_length=10, blank=True)
    activite_principale = models.CharField(max_length=255, blank=True)
    dirigeants         = models.JSONField(default=list, blank=True)
    
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Établissement RIDET"
        verbose_name_plural = "Établissements RIDET"

    def __str__(self):
        return f"{self.rid7} — {self.denomination or self.enseigne}"


# ---------------------------------------------------------------------------
# AIAnalysis
# ---------------------------------------------------------------------------

class AIAnalysis(models.Model):
    """Résultat d'une analyse LLM (Ollama) sur une offre ou une entreprise."""

    job_offer     = models.ForeignKey(
        JobOffer, on_delete=models.CASCADE,
        related_name="ai_analyses", null=True, blank=True
    )
    rid7          = models.CharField(max_length=20, blank=True, db_index=True)
    analysis_type = models.CharField(max_length=50, choices=AIAnalysisType.choices)
    model_used    = models.CharField(max_length=100)
    prompt_hash   = models.CharField(max_length=64, db_index=True)
    result_text   = models.TextField(blank=True)
    result_json   = models.JSONField(null=True, blank=True)
    language      = models.CharField(max_length=20, default="Français")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["job_offer", "analysis_type"]),
            models.Index(fields=["rid7", "analysis_type"]),
        ]
        verbose_name = "Analyse IA"
        verbose_name_plural = "Analyses IA"

    def __str__(self):
        target = f"offre #{self.job_offer_id}" if self.job_offer_id else f"rid7={self.rid7}"
        return f"{self.get_analysis_type_display()} — {target}"


# ---------------------------------------------------------------------------
# PromptTemplate
# ---------------------------------------------------------------------------

class PromptTemplate(models.Model):
    """Template de prompt Ollama géré en base (modifiable via l'admin)."""

    name        = models.SlugField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    template    = models.TextField()
    is_system   = models.BooleanField(
        default=False,
        help_text="True = utilisé comme system prompt Ollama"
    )
    version     = models.PositiveSmallIntegerField(default=1)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Template de prompt"
        verbose_name_plural = "Templates de prompts"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# ScrapeLog
# ---------------------------------------------------------------------------

class ScrapeLog(models.Model):
    """Journal d'une session de scraping (une entrée par source par exécution)."""

    source          = models.CharField(max_length=20, choices=Source.choices)
    started_at      = models.DateTimeField(default=timezone.now)
    finished_at     = models.DateTimeField(null=True, blank=True)
    status          = models.CharField(
        max_length=20, choices=ScrapeStatus.choices, default=ScrapeStatus.RUNNING
    )
    offers_imported = models.PositiveIntegerField(default=0)
    offers_skipped  = models.PositiveIntegerField(default=0)
    error_message   = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Journal de scraping"
        verbose_name_plural = "Journaux de scraping"

    def __str__(self):
        return f"{self.source} — {self.started_at:%Y-%m-%d %H:%M} — {self.status}"

    def finalize(self, imported: int, skipped: int, error: str = ""):
        self.finished_at    = timezone.now()
        self.offers_imported = imported
        self.offers_skipped  = skipped
        self.error_message   = error
        self.status = ScrapeStatus.FAILED if error else ScrapeStatus.SUCCESS
        self.save(update_fields=[
            "finished_at", "offers_imported", "offers_skipped",
            "error_message", "status"
        ])


# ---------------------------------------------------------------------------
# AppParameter
# ---------------------------------------------------------------------------

class AppParameter(models.Model):
    """Paramètre de configuration dynamique clé/valeur (remplace config.yaml)."""

    key         = models.CharField(max_length=100, unique=True, db_index=True)
    value       = models.TextField()
    description = models.CharField(max_length=255, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre"
        verbose_name_plural = "Paramètres"

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key: str, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        val = cls.get(key)
        try:
            return int(val) if val is not None else default
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        val = cls.get(key)
        try:
            return float(val) if val is not None else default
        except (ValueError, TypeError):
            return default
