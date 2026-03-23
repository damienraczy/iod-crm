Voici le protocole complet de traitement d'une opportunité commerciale au sein de l'architecture **iod-crm**, de la détection du besoin à la facturation finale.

## Etapes de traitement
### Phase 1 : La détection (Table `JobOffer`)
Le cycle commence par l'importation automatisée des offres d'emploi. À ce stade, l'information est brute et réside uniquement dans le module **Intelligence Emploi**.
- **Action** : consulter la liste des offres scrapées.
- **Donnée** : le système identifie un besoin d'évaluation (ex : recrutement d'un technicien).
- **Statut** : l'entité n'est pas encore un prospect, c'est un signal de marché.

### Phase 2 : La qualification et l'IA (Table `AiAnalysis`)
Avant d'engager une action humaine, le système prépare le terrain pour le commercial.
- **Analyse Ollama** : déclencher l'IA pour obtenir un diagnostic de l'offre et un email d'accroche (Ice Breaker).
- **Consolidation RIDET** : utiliser le bouton de consolidation pour lier l'offre à une fiche **RidetEntry**. Cela permet de récupérer les coordonnées officielles et les noms des dirigeants sans saisie manuelle.

### Phase 3 : La transformation en prospect (Table `Lead`)
Si le score de priorité est élevé, l'offre est convertie en **Lead**.
- **Le Lead** : c'est un objet temporaire. Il contient le nom de l'entreprise cible et le contact potentiel, mais ne crée pas encore de fiches définitives dans votre base clients.
- **Objectif** : obtenir un premier échange (appel ou réponse à l'email généré par l'IA).
- **Suivi** : le prospect est visible dans le pipeline Kanban en étape _Prospecting_.

### Phase 4 : Le pivot stratégique (La Conversion)
C'est l'étape la plus critique. Lorsque le contact est établi et que le besoin est confirmé, vous cliquez sur **Convertir**. Cette action unique déclenche la création de trois objets distincts et liés :

|**Objet créé**|**Description et usage**|
|---|---|
|**Account** (Compte)|L'entreprise **SAUVAN**. C'est le socle juridique pour la facturation et l'historique à long terme.|
|**Contact**|L'interlocuteur physique (ex : le Responsable de Maintenance). C'est à lui que vous envoyez les rapports d'évaluation.|
|**Opportunity** (Affaire)|Le projet spécifique de vente. C'est ici que vous déterminez le montant et la date de clôture.|

### Phase 5 : Le pilotage de l'opportunité (Table `Opportunity`)
L'affaire est maintenant valorisée techniquement dans le pipeline.
- **Mapping Produit** : sélectionner le produit **eval_n5** dans le catalogue.
- **Valorisation** : le montant s'établit à $50\,000$ FCFP par unité.
- **Probabilité** : ajuster le pourcentage selon l'avancement (Qualification $\rightarrow$ Proposition $\rightarrow$ Négociation).
- **Valeur Pondérée** : le CRM calcule automatiquement votre revenu prévisionnel :
    $$Valeur = Montant \times Probabilité$$

### Phase 6 : La finalisation (Table `Invoice`)
Une fois l'opportunité marquée en **Closed Won** (Gagné), le cycle de vente se termine et le cycle opérationnel débute.
- **Facturation** : transformer l'opportunité en facture (**Invoice**). Les données de l'**Account** (adresse, RIDET) et de l'**Opportunity** (produits, montants) sont importées automatiquement.
- **Support** : si l'évaluation nécessite un suivi particulier, ouvrir un **Case** (Ticket) lié au compte pour la gestion de la prestation.

---

## Synthèse du flux de données
1. **Signal** : `JobOffer` (Scraping).
2. **Préparation** : `AiAnalysis` + `RidetEntry` (IA et Données officielles).
3. **Engagement** : `Lead` (Prospection).
4. **Structure** : `Account` + `Contact` + `Opportunity` (Conversion).
5. **Revenu** : `Invoice` (Clôture).
Je peux vous assister dans la configuration des **PromptTemplates** pour automatiser la rédaction des emails de prospection basés sur vos produits d'évaluation.

