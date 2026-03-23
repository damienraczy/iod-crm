# Guide de Présentation : IOD-CRM (Intelligence Opérationnelle & Décisionnelle)

Ce document présente les fonctionnalités à forte valeur ajoutée ajoutées au socle CRM et l'organisation fonctionnelle du système pour les équipes commerciales.

---

## 1. Les 5 Piliers de Valeur Ajoutée pour la Vente

Le CRM a été transformé pour devenir une véritable station de travail proactive, automatisant la prospection et la préparation des entretiens.

### 🎯 Le "Radar de Prospection" (Intelligence Emploi NC)
Le système effectue une veille automatique sur le marché de l'emploi en Nouvelle-Calédonie (Emploi Gouv, Province Sud, Job.nc, L'Emploi.nc).
*   **Centralisation :** Toutes les offres pertinentes arrivent directement dans l'outil.
*   **Scoring Automatique :** Chaque offre reçoit une note de priorité (0-100) basée sur l'expérience requise, le type de contrat et la formation. Les commerciaux savent immédiatement où investir leur énergie.

### 🤖 L'Assistant IA (Préparation d'Appel via Ollama)
Sur chaque offre d'emploi, une IA locale aide à préparer la démarche commerciale :
*   **Ice Breakers :** Génération de phrases d'accroche personnalisées.
*   **Diagnostic Offre :** Analyse critique des besoins réels de l'entreprise.
*   **Questions Brûlantes :** Liste de questions percutantes pour démontrer son expertise dès le premier appel.
*   **Emails de Prospection :** Rédaction automatique d'emails ultra-personnalisés.

### 🔍 Consolidation Ridet & Infogreffe ("Zéro Saisie")
Un bouton de consolidation permet de récupérer automatiquement les données officielles d'une entreprise :
*   **Fiabilité :** Importation de l'adresse, du code NAF et de l'activité.
*   **Organigramme :** Récupération de la liste des dirigeants officiels et de leurs rôles pour identifier les bons décideurs.

### 📊 Pipelines Kanban & Relances Intelligentes
Le suivi des ventes est visuel et structuré :
*   **Tableaux Kanban :** Gestion par glisser-déposer des prospects à travers des étapes personnalisables.
*   **Détection de Stagnation :** Marquage automatique des leads "froids" (sans contact depuis > 30 jours).
*   **Alertes de Retard :** Visualisation immédiate des relances prioritaires non effectuées.

### 🛡️ Sécurité et Isolation des Données (RLS)
Grâce à la technologie PostgreSQL Row-Level Security :
*   **Confidentialité Totale :** Chaque agence ou organisation ne voit que ses propres données.
*   **Zéro Erreur :** Un commercial d'une entité ne peut jamais accéder par mégarde aux chiffres ou aux leads d'une autre entité.

---

## 2. Organisation des Données (Structure des Tables)

Le CRM est organisé en quatre pôles logiques pour fluidifier le parcours de vente.

### A. Pôle Intelligence (Nouveautés IOD)
*Ces tables gèrent la prospection "amont".*
- **`JobOffer`** : Les opportunités d'emploi détectées sur le web.
- **`RidetEntry`** : L'annuaire officiel des entreprises (RID7) et leurs dirigeants.
- **`AiAnalysis`** : Historique des arguments de vente générés par l'IA.
- **`PromptTemplate`** : Les modèles de comportement de l'IA (personnalisables).

### B. Pôle Ventes & Pipeline
*Ces tables gèrent la transformation des prospects.*
- **`Lead`** : Le contact commercial identifié.
- **`LeadPipeline`** : Les différents tunnels de vente (ex: Inbound vs Outbound).
- **`LeadStage`** : Les étapes (colonnes) de votre tableau de bord.
- **`Opportunity`** : Les affaires en cours avec montant et probabilité de succès.

### C. Pôle Support & Clientèle
*Ces tables gèrent la relation après la vente.*
- **`Account`** : La fiche client officielle (entreprise convertie).
- **`Contact`** : Les personnes physiques au sein des comptes.
- **`Case`** : Tickets de support avec gestion des délais de réponse (SLA).

### D. Pôle Structure
*L'ossature du système.*
- **`Org`** : L'entité (agence) propriétaire des données.
- **`Profile`** : L'utilisateur CRM (commercial, manager).
- **`Teams`** : Groupes de travail pour le partage de leads.

---

## 3. Flux de Travail Idéal (Workflow)

1.  **Détection :** Le commercial consulte les nouvelles **JobOffers** scorées.
2.  **Préparation :** Il génère un **Ice Breaker** et des **Questions Brûlantes** via l'IA.
3.  **Qualification :** Il consolide la fiche entreprise via **Infogreffe** pour trouver le dirigeant.
4.  **Action :** L'offre est convertie en **Lead** et intégrée au **Pipeline Kanban**.
5.  **Closing :** Le lead devient une **Opportunity** jusqu'à la signature finale.
