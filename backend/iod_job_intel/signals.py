"""
Signaux Django pour iod_job_intel.

post_save sur JobOffer : émet un signal personnalisé `job_offer_created`
que django-crm (ou toute autre app) peut connecter sans import direct
de modèles iod_job_intel.
"""

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver

from .models import JobOffer

# Signal public consommable par d'autres apps
job_offer_created = Signal()


@receiver(post_save, sender=JobOffer)
def _emit_job_offer_created(sender, instance, created, **kwargs):
    """Émet job_offer_created uniquement pour les nouvelles offres avec un rid7."""
    if created and instance.rid7:
        job_offer_created.send(
            sender=JobOffer,
            job_offer_id=instance.pk,
            rid7=instance.rid7,
            company_name=instance.company_name,
            title=instance.title,
            source=instance.source,
        )
