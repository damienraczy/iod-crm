Ce document définit le workflow technique pour automatiser le cycle de prospection depuis la détection d'une offre d'emploi jusqu'à la relance téléphonique.

## Workflow : Automatisation de la prospection "Évaluation de personnel"
### Phase 0 : Ingestion et Réconciliation (Matching)
L'objectif est de transformer une donnée brute de scraping en une entité commerciale exploitable.
1. **Scrapping** : Le module de scraping acquière les nouvelles offres.
### Plase 1 : réconciliation RIDET manuelle
L'objectif est de transformer une donnée brute de scraping en une entité commerciale exploitable.
1. **Mapping RIDET** : Une fonction de recherche floue (_fuzzy matching_) compare le nom de l'entreprise de l'offre avec la base `Établissements RIDET`.
    - _Si validé par l'utilisateur_ : L'offre est liée à l'id RIDET existant.
    - _Si échec_ : Le RIDET peut être saisi à la main. 
    - *Dans tous les cas*: RIDET peut être saisi/corrigé manuellement
2. **Lien Offre** : L'objet `Offres d'emploi` est créé, enrichi de sa relation `Foreign Key` vers l'établissement RIDET.
	- quand **RIDET** connu alors il devient alors possible de naviguer vers l'entreprise identifiée par le RIDET (bouton visible).

### Phase 2 : Génération de l'Argumentaire (IA)
1. **Analyse** : Le module `Analyses IA` traite le texte de l'offre d'emploi via un `Templates de prompts` spécifique à l'évaluation de personnel.
2. **Output** : L'IA génère le corps du mail personnalisé (points de tension, compétences critiques).
3. **Stockage** : Le contenu est stocké temporairement dans un champ `draft_email` de l'objet `Lead`.

**Note** : il faut également proposer des "questions brulantes" pour l'entreprises, et donc permettre d'avoir un bouton qui permette de générer ces questions.
L'entreprise doit avoir un champ "description" et un champ "question brulante". Description est saisi à la main. Question brulante calculé par le module IA en prenant en entrée les informations sur l'entreprise.

**Note** : Le module IA qui calcule les questions brulantes pour l'offre prend en entrée la description de l'offre, son intitulé, etc, mais aussi la description de l'entreprise.

**Note** : Le module IA qui calcule le mail prend en entrée le Prénom+Nom+téléphone de l'utilisateur pour le mettre en signature.

### Phase 3 : Création des Objets CRM
À ce stade, une fonction de conversion crée les enregistrements suivants :
1. **Lead** :
    - Nom : [Titre de l'offre] - [Nom Entreprise].
    - Source : IOD Job Intelligence.
    - Lien : `Établissement RIDET` + `Offre d'emploi`.
2. **Opportunity** :
    - Produit : Sélectionner "Évaluation de personnel" avec le niveau estimé dans le catalogue `Products`.
    - Valeur : Prix standard de la prestation.
    - Probabilité : 5% (étape initiale).

### Phase 4 : Exécution de l'Envoi (Email)
C'est ici qu'interviennent les variables de l'expéditeur qui manquent actuellement.
1. **Résolution des Variables** : Le système fusionne :
    - `{{ content_llm }}` : Le corps généré en Phase 2.
    - `{{ sender_first_name }}` : `request.user.first_name`.
    - `{{ sender_last_name }}` : `request.user.last_name`.
    - `{{ sender_contact }}` : `request.user.email` ou téléphone professionnel.
2. **Envoi SES** : Passage par `Django SES` pour l'expédition.
3. **Historisation** : Création automatique d'un `Comments` sur le `Lead` contenant l'email complet envoyé.

### Phase 5 : Ordonnancement du Suivi (Scheduling)
Dès que l'email est marqué comme envoyé avec succès dans `SES Stats` :
1. **Calcul de l'échéance** : $Date du jour + 3 jours ouvrés$.
2. **Création de la Task** :
    - Objet : "Appel relance : [Nom Entreprise]".
    - Type : Phone Call.
    - Relation : Liée à l'objet `Opportunity` et assignée à `request.user`.
    - Priority : High.
3. **Kanban** : La tâche apparaît automatiquement dans le module `Boards` (Board commercial, colonne "À appeler").

## Fonctions et Automatisations à développer
|**Composant**|**Action technique requise**|
|---|---|
|**Logic de Rapprochement**|Script de nettoyage de chaîne (Regex/Levenshtein) pour lier Offre ↔ RIDET.|
|**Générateur de Lead**|Signal Django (`post_save`) sur `Offres d'emploi` pour créer `Lead` + `Opportunity`.|
|**Moteur de Template**|Intégration de `django.template` pour injecter les données du `User` dans le prompt LLM.|
|**Trigger de Tâche**|Fonction `create_follow_up_task` déclenchée par le succès de l'envoi mail.|
