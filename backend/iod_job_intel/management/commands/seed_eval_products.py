"""
Crée (ou met à jour) les 5 produits "Évaluation de personnel" pour chaque org active.
Idempotent : utilise get_or_create sur (sku, org).

Usage :
    python manage.py seed_eval_products
    python manage.py seed_eval_products --org <org_id>   # une org spécifique
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection

from common.rls import get_set_context_sql

EVAL_PRODUCTS = [
    {
        "sku":         "eval_n4",
        "name":        "Évaluation – Personnels d'exécution",
        "description": (
            "Évaluation d'opérateurs, ouvriers, employés et personnels d'exécution "
            "(entretien structuré + tests psychométriques + rapport détaillé complet)"
        ),
        "price":    Decimal("35000"),
    },
    {
        "sku":         "eval_n5",
        "name":        "Évaluation – Techniciens, Maîtrises",
        "description": (
            "Évaluation de techniciens, agents de maîtrise, employés qualifiés "
            "(entretien structuré + tests psychométriques + rapport détaillé complet)"
        ),
        "price":    Decimal("50000"),
    },
    {
        "sku":         "eval_n6",
        "name":        "Évaluation – Managers opérationnels",
        "description": (
            "Évaluation de managers d'équipe, responsables de service, cadres "
            "(entretien structuré + tests psychométriques + rapport détaillé complet)"
        ),
        "price":    Decimal("70000"),
    },
    {
        "sku":         "eval_n7",
        "name":        "Évaluation – Cadres, responsables de département",
        "description": (
            "Évaluation de cadres supérieurs, responsables de direction fonctionnelle "
            "(entretien structuré + tests psychométriques + rapport détaillé complet)"
        ),
        "price":    Decimal("90000"),
    },
    {
        "sku":         "eval_n8",
        "name":        "Évaluation dirigeant / Executive",
        "description": (
            "Évaluation de cadres dirigeants, directeurs généraux, membres de CODIR "
            "(entretien structuré + tests psychométriques + rapport détaillé complet)"
        ),
        "price":    Decimal("110000"),
    },
]


class Command(BaseCommand):
    help = "Seed les produits Évaluation de personnel (eval_n4 → eval_n8) pour chaque org."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            type=str,
            default=None,
            help="ID d'une org spécifique (défaut : toutes les orgs actives)",
        )

    def handle(self, *args, **options):
        from common.models import Org
        from invoices.models import Product

        orgs = Org.objects.all()
        if options["org"]:
            orgs = orgs.filter(pk=options["org"])
            if not orgs.exists():
                self.stderr.write(self.style.ERROR(f"Org '{options['org']}' introuvable."))
                return

        total_created = total_updated = 0

        for org in orgs:
            self.stdout.write(f"Org : {org.name}")
            with connection.cursor() as cursor:
                cursor.execute(get_set_context_sql(), [str(org.id)])
            for p in EVAL_PRODUCTS:
                obj, created = Product.objects.get_or_create(
                    sku=p["sku"],
                    org=org,
                    defaults={
                        "name":        p["name"],
                        "description": p["description"],
                        "price":       p["price"],
                        "currency":    "XPF",
                        "category":    "Évaluation de personnel",
                        "is_active":   True,
                    },
                )
                if not created:
                    # Mettre à jour le nom/prix si le produit existait déjà
                    updated = False
                    for field in ("name", "description", "price", "currency", "category"):
                        if getattr(obj, field) != p.get(field, getattr(obj, field)):
                            setattr(obj, field, p.get(field))
                            updated = True
                    if updated:
                        obj.save()
                        total_updated += 1
                        self.stdout.write(f"  ↻ {p['sku']} mis à jour")
                    else:
                        self.stdout.write(f"  ✓ {p['sku']} déjà à jour")
                else:
                    total_created += 1
                    self.stdout.write(f"  + {p['sku']} créé")

        self.stdout.write(self.style.SUCCESS(
            f"\nTerminé — {total_created} créés, {total_updated} mis à jour."
        ))
