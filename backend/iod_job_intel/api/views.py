"""
Vues API REST pour iod_job_intel.

Authentification : JWT (héritée de django-crm, via DEFAULT_AUTHENTICATION_CLASSES).
Vues en lecture seule sauf :
  - PATCH /offers/{id}/              → mise à jour partielle d'une offre
  - POST  /offers/{id}/ai-<action>/  → génération IA (ai-skill-analysis, ai-ice-breaker,
                                       ai-diagnostic, ai-questions-offre, ai-email-job)
  - POST  /ridet/<rid7>/ai/<action>/ → génération IA niveau entreprise
  - POST  /sync/trigger/             → déclenche une synchronisation synchrone
  - PUT/PATCH /parameters/{key}/     → mise à jour d'un paramètre
"""

import importlib
import json as _json
import logging
import traceback

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import RetrieveModelMixin, UpdateModelMixin, ListModelMixin, DestroyModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet

from iod_job_intel.models import AIAnalysis, AppParameter, JobOffer, RidetEntry, ScrapeLog
from iod_job_intel.api.serializers import (
    AIAnalysisSerializer,
    AppParameterSerializer,
    JobOfferListSerializer,
    JobOfferSerializer,
    RidetEntrySerializer,
    ScrapeLogSerializer,
)
from iod_job_intel.scrapers.infogreffe_nc import InfogreffeScraper
from iod_job_intel.services.ridet_service import RidetService
from iod_job_intel.tasks.ridet_tasks import refresh_ridet_task

logger = logging.getLogger(__name__)


def _default_language(request=None):
    """Langue par défaut : body > AppParameter > 'Français'."""
    if request and request.data.get("language"):
        return request.data["language"]
    return AppParameter.get("ai.default_language", "Français")


def _save_analysis(*, offer=None, rid7="", analysis_type, model, prompt_hash,
                   result_text="", result_json=None, language):
    """Persiste un résultat IA dans AIAnalysis et retourne l'objet créé."""
    return AIAnalysis.objects.create(
        job_offer=offer,
        rid7=rid7 or (offer.rid7 if offer else ""),
        analysis_type=analysis_type,
        model_used=model,
        prompt_hash=prompt_hash,
        result_text=result_text,
        result_json=result_json,
        language=language,
    )


class JobOfferViewSet(ListModelMixin, RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    """
    Offres d'emploi.

    Méthodes autorisées : GET (list/detail), PATCH (mise à jour partielle).
    Actions IA : POST /offers/{id}/ai-skill-analysis/
                 POST /offers/{id}/ai-ice-breaker/
                 POST /offers/{id}/ai-diagnostic/
                 POST /offers/{id}/ai-questions-offre/
                 POST /offers/{id}/ai-email-job/

    Filtres (query params) :
        ?rid7=1234567          → offres d'une entreprise (pivot CRM)
        ?source=JOB_NC         → par source
        ?status=PUBLIEE        → par statut
        ?q=développeur         → recherche fulltext titre + entreprise
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "list":
            return JobOfferListSerializer
        return JobOfferSerializer

    def get_queryset(self):
        qs = JobOffer.objects.all()

        rid7    = self.request.query_params.get("rid7")
        source  = self.request.query_params.get("source")
        status_ = self.request.query_params.get("status")
        q       = self.request.query_params.get("q")

        if rid7:
            qs = qs.filter(rid7=rid7)
        if source:
            qs = qs.filter(source=source)
        if status_:
            qs = qs.filter(status=status_)
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(company_name__icontains=q))

        return qs

    # ── Lecture ──────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="analyses")
    def analyses(self, request, pk=None):
        """GET /api/iod/offers/{id}/analyses/ — analyses IA liées à l'offre."""
        offer = self.get_object()
        qs = AIAnalysis.objects.filter(job_offer=offer).order_by("-created_at")
        return Response(AIAnalysisSerializer(qs, many=True).data)

    # ── Actions IA ────────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="ai-skill-analysis")
    def ai_skill_analysis(self, request, pk=None):
        """
        POST /api/iod/offers/{id}/ai/skill-analysis/
        Identifie les 3 compétences critiques de l'offre.
        Body optionnel : { "language": "Français" }
        """
        offer = self.get_object()
        language = _default_language(request)

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        skills_list = ", ".join(offer.skills_json) if isinstance(offer.skills_json, list) else ""
        try:
            result = ai.analyze_offer(
                title=offer.title,
                experience=offer.experience_req or "",
                skills_list=skills_list,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"skill_analysis:{offer.title}:{skills_list}:{language}")
            analysis = _save_analysis(
                offer=offer,
                analysis_type="skill_analysis",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_json=result,
                result_text=_json.dumps(result, ensure_ascii=False),
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"], url_path="ai-ice-breaker")
    def ai_ice_breaker(self, request, pk=None):
        """
        POST /api/iod/offers/{id}/ai/ice-breaker/
        Génère une phrase d'accroche commerciale.
        Body optionnel : { "language": "Français" }
        """
        offer = self.get_object()
        language = _default_language(request)

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        try:
            result = ai.generate_ice_breaker(
                company_name=offer.company_name or "votre entreprise",
                job_title=offer.title,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"ice_breaker:{offer.company_name}:{offer.title}:{language}")
            analysis = _save_analysis(
                offer=offer,
                analysis_type="ice_breaker",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"], url_path="ai-diagnostic")
    def ai_diagnostic(self, request, pk=None):
        """
        POST /api/iod/offers/{id}/ai/diagnostic/
        Génère un diagnostic qualitatif de l'offre.
        Body optionnel : { "language": "Français" }
        """
        offer = self.get_object()
        language = _default_language(request)

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        try:
            result = ai.diagnose_offer(
                title=offer.title,
                location=offer.location or "",
                description=offer.raw_description or offer.description or "",
                experience=offer.experience_req or "",
                education=offer.education_req or "",
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"diagnostic:{offer.id}:{language}")
            analysis = _save_analysis(
                offer=offer,
                analysis_type="offer_diagnostic",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"], url_path="ai-questions-offre")
    def ai_questions_offre(self, request, pk=None):
        """
        POST /api/iod/offers/{id}/ai/questions-offre/
        Génère les questions brûlantes sur les compétences requises par l'offre.
        Body optionnel : {
            "language": "Français",
            "company_context": "..."  # caractéristiques entreprise (depuis django-crm)
        }
        """
        offer = self.get_object()
        language = _default_language(request)
        company_context = request.data.get("company_context", "")

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        skills = "\n".join(offer.skills_json) if isinstance(offer.skills_json, list) else ""
        activities = "\n".join(offer.activities_json) if isinstance(offer.activities_json, list) else ""

        try:
            result = ai.generate_questions_brulantes_offre(
                title=offer.title,
                education=offer.education_req or "",
                description=offer.description or "",
                skills=skills,
                activities=activities,
                company_context=company_context,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"questions_offre:{offer.id}:{company_context[:50]}:{language}")
            analysis = _save_analysis(
                offer=offer,
                analysis_type="questions_offre",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"], url_path="ai-email-job")
    def ai_email_job(self, request, pk=None):
        """
        POST /api/iod/offers/{id}/ai/email-job/
        Génère un email de prospection lié à cette offre.
        Body : {
            "questions_brulantes": "...",  # requis (depuis une analyse questions_offre)
            "contact_name": "...",          # optionnel
            "language": "Français"
        }
        """
        offer = self.get_object()
        language = _default_language(request)
        questions = request.data.get("questions_brulantes", "").strip()
        contact_name = request.data.get("contact_name", "Madame, Monsieur")

        if not questions:
            # Tente de récupérer depuis la dernière analyse questions_offre
            last = AIAnalysis.objects.filter(
                job_offer=offer, analysis_type="questions_offre"
            ).order_by("-created_at").first()
            if last:
                questions = last.result_text
            else:
                return Response(
                    {"error": "Fournissez 'questions_brulantes' ou générez d'abord une analyse questions-offre."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        source_label = AppParameter.get(f"source.{offer.source}", default=offer.source)

        try:
            result = ai.generate_email(
                title=offer.title,
                source=source_label,
                contact_name=contact_name,
                questions_brulantes=questions,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"email_job:{offer.id}:{questions[:50]}:{language}")
            analysis = _save_analysis(
                offer=offer,
                analysis_type="email_job",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class CompanyAIView(APIView):
    """
    Génération IA au niveau entreprise (via rid7).

    POST /api/iod/ridet/<rid7>/ai/questions-company/
    POST /api/iod/ridet/<rid7>/ai/email-general/
    """
    permission_classes = [IsAuthenticated]

    def _get_rid7(self, rid7: str):
        """Retourne le RidetEntry si trouvé, sinon None."""
        try:
            return RidetEntry.objects.get(rid7=rid7)
        except RidetEntry.DoesNotExist:
            return None

    def post(self, request, rid7: str, ai_action: str):
        language = request.data.get("language") or AppParameter.get("ai.default_language", "Français")
        entry = self._get_rid7(rid7)
        company_name = entry.denomination if entry else rid7

        from iod_job_intel.services.ai_service import AIService
        ai = AIService()

        if ai_action == "questions-company":
            return self._questions_company(request, rid7, company_name, ai, language)
        elif ai_action == "email-general":
            return self._email_general(request, rid7, company_name, ai, language)
        return Response({"error": f"Action IA inconnue : {ai_action}"}, status=status.HTTP_400_BAD_REQUEST)

    def _questions_company(self, request, rid7, company_name, ai, language):
        """
        Questions brûlantes sur les capacités organisationnelles de l'entreprise.
        Body : {
            "offer_title": "...",       # titre de l'offre de contexte
            "description": "...",       # description de l'offre
            "company_context": "..."    # caractéristiques entreprise (depuis django-crm)
        }
        """
        offer_title = request.data.get("offer_title", "")
        description = request.data.get("description", "")
        company_context = request.data.get("company_context", "")

        try:
            result = ai.generate_questions_brulantes(
                title=offer_title,
                description=description,
                company_context=company_context,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"questions_company:{rid7}:{offer_title}:{language}")
            analysis = _save_analysis(
                rid7=rid7,
                analysis_type="questions_company",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    def _email_general(self, request, rid7, company_name, ai, language):
        """
        Email de prospection général (sans offre spécifique).
        Body : {
            "questions_brulantes": "...",   # requis ou auto-récupéré depuis dernière analyse
            "contact_name": "..."
        }
        """
        questions = request.data.get("questions_brulantes", "").strip()
        contact_name = request.data.get("contact_name", "Madame, Monsieur")

        if not questions:
            last = AIAnalysis.objects.filter(
                rid7=rid7, analysis_type="questions_company"
            ).order_by("-created_at").first()
            if last:
                questions = last.result_text
            else:
                return Response(
                    {"error": "Fournissez 'questions_brulantes' ou générez d'abord une analyse questions-company."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = ai.generate_email_general(
                company_name=company_name,
                contact_name=contact_name,
                questions_brulantes=questions,
                language=language,
            )
            prompt_hash = ai._hash_prompt(f"email_general:{rid7}:{questions[:50]}:{language}")
            analysis = _save_analysis(
                rid7=rid7,
                analysis_type="email_general",
                model=ai._current_model(),
                prompt_hash=prompt_hash,
                result_text=result,
                language=language,
            )
            return Response(AIAnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class AIAnalysisViewSet(ReadOnlyModelViewSet, DestroyModelMixin):
    """Analyses IA — lecture + suppression."""
    permission_classes   = [IsAuthenticated]
    serializer_class     = AIAnalysisSerializer
    http_method_names    = ["get", "delete", "head", "options"]

    def get_queryset(self):
        qs    = AIAnalysis.objects.all()
        rid7  = self.request.query_params.get("rid7")
        atype = self.request.query_params.get("type")
        if rid7:
            qs = qs.filter(rid7=rid7)
        if atype:
            qs = qs.filter(analysis_type=atype)
        return qs.order_by("-created_at")


# ---------------------------------------------------------------------------
# Helpers partagés — Account + Contacts depuis RIDET
# ---------------------------------------------------------------------------

def _parse_dirigeant(raw: str):
    """Parse 'Prénom Nom (Titre)' → (first_name, last_name, title)."""
    title = ""
    name_part = raw.strip()
    if name_part.endswith(")") and "(" in name_part:
        paren_start = name_part.rfind("(")
        title = name_part[paren_start + 1:-1].strip()
        name_part = name_part[:paren_start].strip()
    parts = name_part.split()
    if not parts:
        return "", "", title
    if len(parts) == 1:
        return "", parts[0], title
    return " ".join(parts[:-1]), parts[-1], title


def _ensure_crm_account(rid7: str, org, user, profile):
    """
    Trouve ou crée l'Account CRM pour un RID7, puis synchronise les contacts
    dirigeants depuis RidetEntry. Retourne (account, account_created, contacts_data).
    """
    from accounts.models import Account
    from contacts.models import Contact

    account = Account.objects.filter(rid7=rid7, org=org).first()
    account_created = False

    if not account:
        ridet = RidetEntry.objects.filter(rid7=rid7).first()
        name = (ridet.denomination or ridet.enseigne or rid7) if ridet else rid7
        city = ridet.commune if ridet else ""

        base_name = name
        suffix = 1
        while Account.objects.filter(name__iexact=name, org=org).exists():
            name = f"{base_name} ({suffix})"
            suffix += 1

        account = Account.objects.create(
            name=name,
            rid7=rid7,
            city=city,
            description=f"Créé depuis l'offre Job Intel — RIDET {rid7}",
            org=org,
            created_by=user,
        )
        account.assigned_to.add(profile)
        account_created = True

    # Contacts dirigeants
    ridet = RidetEntry.objects.filter(rid7=rid7).first()
    contacts_data = []
    if ridet and ridet.dirigeants:
        for raw in ridet.dirigeants:
            first_name, last_name, title = _parse_dirigeant(raw)
            if not last_name:
                continue
            contact, _ = Contact.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                org=org,
                defaults={
                    "title": title,
                    "organization": account.name,
                    "account": account,
                    "created_by": user,
                },
            )
            if contact.account_id != account.id:
                contact.account = account
                contact.save(update_fields=["account"])
            contacts_data.append({
                "id": str(contact.id),
                "name": f"{first_name} {last_name}".strip(),
                "title": contact.title or "",
            })

    return account, account_created, contacts_data


class RidetCRMAccountView(APIView):
    """
    Cherche ou crée un Account CRM depuis un RIDET.

    GET  /api/iod/ridet/<rid7>/crm-account/
         → {"found": true/false, "account": {id, name, rid7}}
    POST /api/iod/ridet/<rid7>/crm-account/
         → crée l'Account si inexistant, retourne {created, account, contacts}
    """
    permission_classes = [IsAuthenticated]

    def _account_data(self, account):
        return {"id": str(account.id), "name": account.name, "rid7": account.rid7}

    def get(self, request, rid7: str):
        from accounts.models import Account
        account = Account.objects.filter(rid7=rid7, org=request.profile.org).first()
        if account:
            return Response({"found": True, "account": self._account_data(account)})
        return Response({"found": False, "account": None})

    def post(self, request, rid7: str):
        account, created, contacts_data = _ensure_crm_account(
            rid7, request.profile.org, request.profile.user, request.profile
        )
        return Response(
            {
                "created": created,
                "account": self._account_data(account),
                "contacts": contacts_data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RidetSearchView(APIView):
    """
    Recherche dans le référentiel RIDET.

    GET /api/iod/ridet/search/?q=Air+Caledonie
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q or len(q) < 2:
            return Response(
                {"detail": "Paramètre 'q' requis (min 2 caractères)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entries = RidetEntry.objects.filter(
            Q(denomination__icontains=q) | Q(enseigne__icontains=q) | Q(sigle__icontains=q)
        )[:50]
        return Response(RidetEntrySerializer(entries, many=True).data)


class StartActionView(APIView):
    """
    Orchestre la création d'une action commerciale depuis une offre Job Intel.

    POST /api/iod/offers/<pk>/start-action/

    Étapes :
      1. Classifie l'offre → eval_nX  (sauvegardé sur l'offre)
      2. Trouve ou crée l'Account CRM + Contacts dirigeants
      3. Trouve le produit eval_nX de l'org

    Retourne tout en une réponse. L'humain valide et crée ensuite l'opportunité.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        from iod_job_intel.models import EVAL_CATEGORY_LABELS
        from iod_job_intel.services.ai_service import AIService

        offer = JobOffer.objects.filter(pk=pk).first()
        if not offer:
            return Response({"detail": "Offre introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not offer.rid7:
            return Response(
                {"detail": "Cette offre n'a pas de RID7 — impossible de créer une action commerciale."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        org = request.profile.org

        # ── 1. Classification ──────────────────────────────────────────────────
        try:
            svc = AIService()
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            code = svc.classify_offer(
                title=offer.title,
                description=offer.description,
                qualification=offer.qualification,
                experience=offer.experience_req,
            )
        except RuntimeError as e:
            logger.error("[start-action] classify #%s : %s", pk, e)
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        offer.eval_category = code
        offer.save(update_fields=["eval_category", "updated_at"])

        # ── 2. Account + Contacts ──────────────────────────────────────────────
        account, account_created, contacts_data = _ensure_crm_account(
            offer.rid7, org, request.profile.user, request.profile
        )

        # ── 3. Produit eval_nX ─────────────────────────────────────────────────
        product_data = None
        try:
            from invoices.models import Product
            product = Product.objects.get(sku=code, org=org)
            product_data = {
                "id": str(product.id),
                "name": product.name,
                "price": str(product.price),
                "currency": product.currency,
            }
        except Exception:
            pass  # non-bloquant : le produit peut ne pas exister encore

        return Response({
            "eval_category": {
                "code": code,
                "label": EVAL_CATEGORY_LABELS.get(code, code),
            },
            "account": {
                "id": str(account.id),
                "name": account.name,
                "rid7": account.rid7,
                "created": account_created,
            },
            "contacts": contacts_data,
            "product": product_data,
        })


class ClassifyOfferView(APIView):
    """
    Classifie une offre d'emploi via le LLM classificateur (ministral-3b-cloud).

    POST /api/iod/offers/<pk>/classify/
    → {"code": "eval_n5", "label": "Techniciens, agents de maîtrise"}
    Sauvegarde le résultat dans JobOffer.eval_category.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        from iod_job_intel.models import EVAL_CATEGORY_LABELS
        from iod_job_intel.services.ai_service import AIService

        offer = JobOffer.objects.filter(pk=pk).first()
        if not offer:
            return Response({"detail": "Offre introuvable."}, status=status.HTTP_404_NOT_FOUND)

        try:
            svc = AIService()
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            code = svc.classify_offer(
                title=offer.title,
                description=offer.description,
                qualification=offer.qualification,
                experience=offer.experience_req,
            )
        except RuntimeError as e:
            logger.error("[classify] offre #%s : %s", pk, e)
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        offer.eval_category = code
        offer.save(update_fields=["eval_category", "updated_at"])

        return Response({
            "code": code,
            "label": EVAL_CATEGORY_LABELS.get(code, code),
        })


class ScrapeLogViewSet(ReadOnlyModelViewSet):
    """Journal de scraping — lecture seule."""
    permission_classes = [IsAuthenticated]
    serializer_class   = ScrapeLogSerializer

    def get_queryset(self):
        qs     = ScrapeLog.objects.all()
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source=source)
        return qs[:50]


class SyncTriggerView(APIView):
    """
    Déclenche une synchronisation synchrone (bloquante).
    À terme, remplacée par une tâche Celery.

    POST /api/iod/sync/trigger/
    Body JSON : {"sources": ["GOUV_NC", "PSUD"], "limit": 20}
    """
    permission_classes = [IsAuthenticated]

    SCRAPERS = {
        "GOUV_NC":    ("iod_job_intel.scrapers.gouv_nc",    "GouvNCScraper"),
        "PSUD":       ("iod_job_intel.scrapers.province_sud", "ProvinceSudScraper"),
        "JOB_NC":     ("iod_job_intel.scrapers.job_nc",     "JobNCScraper"),
        "LEMPLOI_NC": ("iod_job_intel.scrapers.lemploi_nc", "LemploiNCScraper"),
    }

    def post(self, request):
        sources = request.data.get("sources", list(self.SCRAPERS.keys()))
        limit   = request.data.get("limit", None)
        days    = request.data.get("days", None)

        results = {}
        for source in sources:
            if source not in self.SCRAPERS:
                results[source] = {"error": "Source inconnue"}
                continue
            module_path, class_name = self.SCRAPERS[source]
            try:
                module  = importlib.import_module(module_path)
                scraper = getattr(module, class_name)()
                kwargs  = {}
                if limit:
                    kwargs["limit"] = limit
                if days and source == "JOB_NC":
                    kwargs["days"] = days
                stats = scraper.run(**kwargs)
                results[source] = stats
            except Exception as exc:
                results[source] = {"error": str(exc)}

        return Response({"results": results}, status=status.HTTP_200_OK)


class AppParameterViewSet(ModelViewSet):
    """Paramètres de configuration — lecture et mise à jour."""
    permission_classes   = [IsAuthenticated]
    serializer_class     = AppParameterSerializer
    queryset             = AppParameter.objects.all().order_by("key")
    lookup_field         = "key"
    lookup_value_regex   = r"[^/]+"
    http_method_names    = ["get", "put", "patch", "head", "options"]


class RidetMatchView(APIView):
    """
    Recherche intelligente de RIDET (Exacte puis Floue).
    GET /api/iod/ridet/match/?q=...
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = request.query_params.get("q", "")
        if len(q) < 2:
            return Response(
                {"detail": "Paramètre 'q' requis (min 2 caractères)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        results = RidetService.match_company(q)
        return Response(results)


class RidetConsolidateView(APIView):
    """
    Consolide les données d'un établissement via Infogreffe.nc.
    POST /api/iod/ridet/<rid7>/consolidate/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, rid7):
        try:
            entry, _ = RidetEntry.objects.get_or_create(rid7=rid7)

            data = InfogreffeScraper(rid7).run()

            if not data:
                return Response(
                    {"detail": "Établissement non trouvé sur Infogreffe.nc. Vérifiez le numéro RID7."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            entry.adresse = data.get("adresse", "")
            entry.code_naf = data.get("code_naf", "")
            entry.activite_principale = data.get("activite_principale", "")
            entry.dirigeants = data.get("dirigeants", [])
            # update_fields explicite : description (saisi manuellement) n'est jamais écrasé
            entry.save(update_fields=["adresse", "code_naf", "activite_principale", "dirigeants", "updated_at"])

            return Response(RidetEntrySerializer(entry).data)
        except Exception as e:
            logger.error(f"CRASH Consolidation RIDET {rid7}: {e}\n{traceback.format_exc()}")
            return Response(
                {"detail": f"Erreur lors de la consolidation : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RidetExtractView(APIView):
    """
    Consolide un établissement depuis avisridet.isee.nc (PDF → LLM → JSON).
    POST /api/iod/ridet/<rid7>/extract-ridet/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, rid7):
        from iod_job_intel.scrapers.avisridet_nc import AvisRidetScraper
        from iod_job_intel.services.ai_service import AIService

        try:
            entry, _ = RidetEntry.objects.get_or_create(rid7=rid7)

            pdf_text = AvisRidetScraper(rid7).run()
            if not pdf_text:
                return Response(
                    {"detail": "Aucun document trouvé sur avisridet.isee.nc pour ce RID7."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            data = AIService().extract_ridet_pdf(pdf_text)

            entreprise   = data.get("entreprise") or {}
            etablissement = data.get("etablissement") or {}

            # Mise à jour des champs — description jamais écrasée
            update_fields = ["updated_at"]
            def _set(field, value):
                if value:
                    setattr(entry, field, value)
                    update_fields.append(field)

            _set("denomination",        entreprise.get("raison_sociale", ""))
            _set("sigle",               entreprise.get("sigle", ""))
            _set("forme_juridique",     entreprise.get("forme_juridique", ""))
            _set("enseigne",            etablissement.get("enseigne", ""))
            _set("adresse",             etablissement.get("adresse", ""))
            _set("commune",             etablissement.get("ville", ""))
            _set("code_naf",            etablissement.get("code_ape", ""))
            _set("activite_principale", etablissement.get("libelle_APE", "")
                                        or etablissement.get("activite_principale (APE)", ""))

            entry.save(update_fields=list(set(update_fields)))

            return Response({
                "entry": RidetEntrySerializer(entry).data,
                "raw": data,
            })
        except Exception as e:
            logger.error(f"CRASH RidetExtract {rid7}: {e}\n{traceback.format_exc()}")
            return Response(
                {"detail": f"Erreur : {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RidetDetailView(APIView):
    """
    GET   /api/iod/ridet/<rid7>/  → détails d'un établissement
    PATCH /api/iod/ridet/<rid7>/  → mise à jour de la description uniquement
    """
    permission_classes = [IsAuthenticated]

    def _get_entry(self, rid7):
        try:
            return RidetEntry.objects.get(rid7=rid7)
        except RidetEntry.DoesNotExist:
            return None

    def get(self, request, rid7):
        entry = self._get_entry(rid7)
        if not entry:
            return Response({"detail": "Non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        return Response(RidetEntrySerializer(entry).data)

    def patch(self, request, rid7):
        entry = self._get_entry(rid7)
        if not entry:
            return Response({"detail": "Non trouvé"}, status=status.HTTP_404_NOT_FOUND)
        # Seul le champ description est modifiable via cet endpoint
        description = request.data.get("description")
        if description is None:
            return Response({"detail": "Champ 'description' requis."}, status=status.HTTP_400_BAD_REQUEST)
        entry.description = description
        entry.save(update_fields=["description", "updated_at"])
        return Response(RidetEntrySerializer(entry).data)


class RidetRefreshView(APIView):
    """
    Déclenche le rafraîchissement asynchrone du RIDET.
    POST /api/iod/ridet/refresh/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if AppParameter.get("ridet_import_status") == "RUNNING":
            return Response(
                {"detail": "Un import est déjà en cours."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_ridet_task.delay()
        return Response(
            {"detail": "Mise à jour du RIDET lancée en arrière-plan."},
            status=status.HTTP_202_ACCEPTED,
        )
