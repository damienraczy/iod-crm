# Guide Utilisateur — Intelligence Emploi NC

Module `iod_job_intel` intégré à Django-CRM.
Collecte les offres d'emploi publiées en Nouvelle-Calédonie, les analyse par IA et alimente la prospection commerciale.

---

## Accéder au module

Dans la barre latérale gauche, cliquer sur **Intelligence** → le menu se déplie en trois entrées :

| Entrée | Page |
|--------|------|
| Offres d'emploi | Liste filtrée des offres collectées |
| Logs scraping | Historique des synchronisations |
| Paramètres | Configuration du module |

---

## Page Offres d'emploi

### Vue d'ensemble

La page affiche toutes les offres collectées. Le compteur en haut indique le nombre total et les filtres actifs.

### Filtres

Trois filtres disponibles, cumulables :

| Filtre | Description |
|--------|-------------|
| Champ de recherche | Recherche sur le titre et le nom d'entreprise — valider avec **Entrée** |
| Source | Filtre par source : Emploi Gouv NC / Province Sud / Job.nc / L'Emploi.nc |
| Statut | Nouvelle / Publiée / Archivée |

Les filtres sont encodés dans l'URL : la page peut être mise en favori ou partagée telle quelle.
Cliquer **Effacer** pour réinitialiser tous les filtres.

### Colonnes du tableau

| Colonne | Description |
|---------|-------------|
| Titre | Intitulé du poste |
| Entreprise | Nom brut scraped + RID7 (si disponible) |
| Source | Origine (badge coloré) |
| Contrat | Type de contrat |
| Statut | NEW / PUBLIEE / ARCHIVEE (badge coloré) |
| Score | Score de priorité de 0 à 100 — vert ≥ 70, orange ≥ 40, gris < 40 |
| Publiée | Date de publication |
| ↗ | Lien direct vers l'offre originale (ouvre un nouvel onglet) |

Le **score** est calculé automatiquement à l'import selon l'expérience requise, le type de contrat, la formation et le nombre de postes.

### Synchronisation

Bouton **Synchroniser** en haut à droite → menu déroulant :

- **Toutes les sources** — lance toutes les sources en séquence
- Source individuelle — lance uniquement la source choisie

La synchronisation est synchrone : le bouton tourne pendant l'opération. Un toast confirme le lancement. Les nouveaux résultats apparaissent après rafraîchissement.

---

## Drawer de détail (clic sur une offre)

Cliquer sur n'importe quelle ligne ouvre un panneau latéral à droite avec **trois onglets**.

### Onglet Détail

Affiche les informations structurées de l'offre :

- Source, statut, contrat, score, localisation, date de publication
- RID7 (identifiant RIDET de l'établissement employeur)
- Description complète
- **Analyses IA enregistrées** : toutes les analyses générées précédemment pour cette offre, avec le type d'analyse et le modèle utilisé

### Onglet Éditer Offre

Permet de modifier manuellement les champs de l'offre :

| Champ | Description |
|-------|-------------|
| Titre | Intitulé du poste |
| Localisation | Lieu du poste |
| Contrat | Type de contrat (liste) |
| Expérience requise | Texte libre |
| Nb postes | Nombre de postes à pourvoir |
| Score | Score de priorité manuel (0-100) |
| Statut | NEW / PUBLIEE / ARCHIVEE |
| Formation requise | Niveau ou descriptif |
| Description | Texte complet de l'offre |

Cliquer **Enregistrer** pour sauvegarder. Les modifications sont immédiatement prises en compte dans la liste.

### Onglet Actions IA

Permet de générer des analyses via le LLM local (Ollama). Les résultats sont **sauvegardés automatiquement** dans la base de données — ils apparaissent ensuite dans l'onglet Détail.

#### Actions sur l'offre

| Bouton | Ce qui est généré | Utilisation commerciale |
|--------|-------------------|------------------------|
| **Compétences critiques** | Les 3 compétences clés que l'entreprise cherche vraiment | Identifier les besoins réels au-delà du descriptif |
| **Ice breaker** | Une phrase d'accroche personnalisée entreprise + poste | Ouvrir un email ou un appel |
| **Diagnostic offre** | Analyse critique de la qualité de l'offre | Comprendre la maturité RH de l'entreprise |
| **Questions brûlantes** | Questions percutantes sur les exigences de l'offre | Structurer un entretien de découverte |
| **Email prospection** | Email complet personnalisé lié à cette offre | Prêt à envoyer, basé sur les questions brûlantes |

> **Astuce :** Pour l'email de prospection, générer d'abord les **Questions brûlantes** — l'email les incorpore automatiquement. Si aucune analyse questions-offre n'existe encore, un message d'erreur vous l'indique.

#### Actions sur l'entreprise (nécessite un RID7)

Ces boutons n'apparaissent que si l'offre a un RID7 associé.

| Bouton | Ce qui est généré |
|--------|-------------------|
| **Questions entreprise** | Questions sur les capacités organisationnelles de l'entreprise |
| **Email général** | Email de prospection sans lien à une offre spécifique |

> **Note :** Si l'offre n'a pas de RID7, un message explicatif s'affiche à la place des boutons. Il faut d'abord associer l'entreprise au référentiel RIDET (via l'admin Django `/admin/iod_job_intel/joboffer/`).

#### Résultat généré

Après génération :
- Le résultat s'affiche dans la zone grise en bas
- Un bouton **Copier** permet de copier le texte dans le presse-papier
- L'analyse est automatiquement ajoutée à la liste dans l'onglet Détail

---

## Page Logs de scraping

Historique de toutes les synchronisations avec :

| Colonne | Description |
|---------|-------------|
| Statut | ✓ Succès / ⚠ Partiel / ✗ Échec / ⟳ En cours |
| Source | Source concernée |
| Démarré | Date et heure de début |
| Durée | Durée de la session (secondes ou minutes) |
| Importées | Nombre de nouvelles offres enregistrées |
| Ignorées | Offres déjà connues (doublons) |
| Erreur | Message d'erreur éventuel (survol pour détail complet) |

Le filtre en haut à droite permet de n'afficher qu'une seule source.

Un statut **Partiel** indique que la session a importé des offres mais a rencontré des erreurs sur certaines.
Un statut **Échec** indique que le scraper a planté — le message d'erreur précise la cause (souvent un changement de structure du site cible).

---

## Page Paramètres

Tableau des paramètres de configuration du module, modifiables sans redéploiement.

### Modifier un paramètre

1. Cliquer sur la ligne du paramètre → un champ de saisie apparaît à droite
2. Modifier la valeur
3. Appuyer sur **Entrée** pour sauvegarder, ou **Échap** pour annuler

### Paramètres disponibles

| Clé | Description | Valeur par défaut |
|-----|-------------|-------------------|
| `ai.default_model` | Modèle Ollama utilisé pour toutes les analyses | `llama3.2:latest` |
| `ai.default_language` | Langue des réponses IA | `Français` |
| `scraper.gouv_nc.limit` | Nb max d'offres importées depuis Emploi Gouv NC | `50` |
| `scraper.psud.limit` | Nb max depuis Province Sud | `10` |
| `scraper.jobnc.anteriorite_jours` | Fenêtre de rétroactivité Job.nc (jours) | `30` |
| `scraper.lemploinc.limit` | Nb max depuis L'Emploi.nc | `10` |

> **Note :** Les paramètres sont lus à chaque exécution — une modification est effective immédiatement sans redémarrage du serveur.

---

## Administration Django (accès avancé)

L'interface d'administration Django à `/admin/` donne accès direct aux tables :

| Table admin | Usage |
|-------------|-------|
| `iod_job_intel > Job offers` | Voir/modifier/supprimer des offres, rechercher par RID7 |
| `iod_job_intel > Ridet entries` | Rechercher une entreprise par nom ou RID7 |
| `iod_job_intel > AI analyses` | Historique complet de toutes les analyses générées |
| `iod_job_intel > Prompt templates` | Modifier les templates de prompts sans redéploiement |
| `iod_job_intel > Scrape logs` | Historique détaillé des synchronisations |
| `iod_job_intel > App parameters` | Alternative à la page Paramètres |

---

## Questions fréquentes

**Le bouton Synchroniser ne fait rien / tourne longtemps**
La synchronisation est synchrone — elle peut durer 1 à 5 minutes selon les sources. Consulter les Logs de scraping pour voir le résultat. Si une source échoue régulièrement, consulter le message d'erreur dans les logs.

**L'analyse IA génère une erreur**
Vérifier qu'Ollama est démarré : `ollama list` dans un terminal. Vérifier l'URL configurée dans les paramètres (`ai.default_model`) ou dans les variables d'environnement (`OLLAMA_BASE_URL`).

**Une offre n'a pas de RID7**
Le scraper n'a pas pu faire correspondre le nom de l'entreprise au référentiel RIDET. Pour l'associer manuellement : aller dans `/admin/iod_job_intel/joboffer/`, ouvrir l'offre, saisir le RID7 dans le champ correspondant.

**Le score d'une offre est à 0**
Le scoring automatique nécessite que les champs `experience_req`, `contract_type` et `education_req` soient renseignés. Si le scraper n'a pas extrait ces données, le score reste à 0 et peut être saisi manuellement via l'onglet "Éditer Offre".
