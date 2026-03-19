Voici les principes de développement à respecter pour personnaliser votre CRM tout en garantissant la possibilité de fusionner les futures mises à jour officielles via GitHub.

---

### 1. Isolation stricte du code
* **Backend :** Ne modifiez jamais les fichiers des applications natives (ex: `accounts`, `leads`). Placez toute votre logique dans votre application dédiée `iod_job_intel`.
* **Frontend :** Ne modifiez pas les composants de base dans `src/lib/components/ui/`. Créez vos propres composants dans un sous-dossier `src/lib/components/custom/`.

### 2. Extension par héritage et relations
* **Modèles :** Si vous devez ajouter des données à un "Lead", ne modifiez pas le fichier `models.py` de l'application `leads`. Créez un modèle dans votre application `iod_job_intel` avec une `OneToOneField` pointant vers le Lead original.
* **Routes :** Créez des dossiers de routes exclusifs pour vos fonctionnalités (ex: `src/routes/(app)/job-intel/`) au lieu d'injecter du code dans les pages existantes.

### 3. Externalisation de la configuration
* **Variables d'environnement :** Ne mettez aucune valeur "en dur" (URL d'API, clés privées, modèles Ollama) dans le code. Utilisez exclusivement le fichier `.env`.
* **Settings Django :** Si vous devez ajouter des applications ou des middlewares dans `settings.py`, faites-le à la fin du fichier avec des commentaires clairs pour faciliter le report lors d'un conflit de mise à jour.

### 4. Utilisation des Points d'Entrée (Hooks)
* **API :** Utilisez les "Signals" de Django pour déclencher des actions (ex: créer une offre d'emploi dès qu'un prospect est qualifié) sans modifier le code de qualification du prospect.
* **Frontend :** Si vous devez ajouter un bouton sur une page existante, documentez précisément la ligne modifiée. C'est le seul cas où un conflit `git` sera inévitable.

### 5. Stratégie Git rigoureuse
* **Branche de travail :** Ne travaillez jamais sur la branche `main`. Créez une branche `prod-custom`.
* **Mise à jour :** Pour mettre à jour, faites un `git pull origin main` sur votre branche `main` propre, puis faites un `git merge main` vers votre branche `prod-custom`.
* **Conflits :** En respectant les points 1 et 2, les seuls conflits possibles concerneront `settings.py` et les fichiers de routage, ce qui se résout en quelques secondes.

---

### Résumé technique pour une mise à jour sans douleur

| Élément | Action |
| :--- | :--- |
| **Nouveaux champs** | Créer une table liée (Relation) |
| **Nouveaux écrans** | Créer un nouveau dossier dans `src/routes/` |
| **Logique métier** | Créer une application Django séparée |
| **Style visuel** | Utiliser les classes Tailwind du Design System |

En suivant cette méthode, vous traitez le CRM d'origine comme une bibliothèque externe que vous ne faites qu'étendre, et non comme un bloc monolithique que vous transformez.