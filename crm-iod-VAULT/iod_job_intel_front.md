# Guide d'utilisation Frontend : iod_job_intel

Cette notice explique comment consommer les données d'intelligence marché (offres d'emploi et analyses IA) dans le frontend SvelteKit.

## 1. Structure de l'API
Toutes les données sont accessibles via le préfixe `/api/iod/`.

### Points d'entrée (Endpoints)
| Ressource | URL | Action |
| :--- | :--- | :--- |
| **Offres d'emploi** | `/api/iod/offers/` | Liste paginée, recherche, filtrage |
| **Analyses IA** | `/api/iod/analyses/` | Analyses détaillées liées aux offres |
| **Recherche RIDET** | `/api/iod/ridet/search/` | Recherche par nom ou rid7 dans le référentiel |
| **Logs de scraping** | `/api/iod/logs/` | Suivi de l'état des collectes |

---

## 2. Consommation des données (Exemple SvelteKit)

### Récupérer les offres d'emploi (`+page.server.js`)
Pour afficher les offres dans une page, utilisez le client API existant ou `fetch` :

```javascript
/** @type {import('./$types').PageServerLoad} */
export async function load({ fetch }) {
  const response = await fetch('/api/iod/offers/?status=NEW&ordering=-date_published');
  const jobs = await response.json();
  
  return { jobs };
}
```

### Champs disponibles pour une offre (`JobOffer`)
| Champ | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Identifiant interne unique |
| `title` | String | Titre du poste |
| `company_name` | String | Nom de l'entreprise (tel que publié) |
| `rid7` | String | Clé de liaison vers le CRM (RIDET) |
| `score` | Integer | Priorité calculée (0-100) |
| `contract_type`| String | CDI, CDD, etc. |
| `date_published`| DateTime | Date de mise en ligne |
| `status` | String | `NEW`, `PUBLIEE` ou `ARCHIVEE` |

---

## 3. Liaison avec les comptes du CRM
La liaison entre une offre d'emploi et une entreprise du CRM se fait via le champ **`rid7`**.

```javascript
// Exemple de filtrage des offres pour un compte spécifique
const accountRidet = "1234567";
const jobsForAccount = await fetch(`/api/iod/offers/?rid7=${accountRidet}`);
```

---

## 4. Filtrage et Recherche (Query Params)
Le module `JobOfferViewSet` supporte les filtres suivants :
- `?source=JOB_NC` : Filtrer par source.
- `?status=NEW` : Uniquement les nouvelles offres.
- `?score_gt=50` : Offres à fort potentiel.
- `?search=commercial` : Recherche plein texte (titre/description).
- `?ordering=-score` : Trier par score décroissant.

---

## 5. Déclenchement manuel du Scraping
Vous pouvez créer un bouton d'administration pour forcer une mise à jour :

```javascript
// Action POST vers le trigger
async function triggerSync() {
  await fetch('/api/iod/sync/trigger/', {
    method: 'POST',
    body: JSON.stringify({ source: 'ALL' })
  });
}
```

---

## 6. Composants UI recommandés
- **Badge de Score** : Utiliser un code couleur selon la valeur (Vert > 70, Orange 40-70, Rouge < 40).
- **Lien Source** : Toujours proposer le lien `url_external` pour consulter l'annonce originale.
- **Indicateur de statut** : Afficher clairement si une offre est déjà "Traitée" ou "Nouvelle".
