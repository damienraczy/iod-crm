
# LEAD_SOURCE

| Code       | site web            | libellé du site                |
| ---------- | ------------------- | ------------------------------ |
| JOB_NC     | www.job.nc          | site job.nc                    |
| GOUV_NC    | www.emploi.gouv.nc  | site emploi de gouv.nc         |
| PSUD       | www.province-sud.nc | site emploi de la Province Sud |
| LEMPLOI_NC | www.lemploi.nc      | site lemploi.nc                |

# Produit "Évaluation de personnel"


| Code    | Libellé                                          | Description                                                                                                                                       | Prix        |
| ------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| eval_n4 | Évaluation – Personnels d'exécution              | Évaluation d'opérateurs, ouvriers, employés et personnels d'exécution (entretien structuré + tests psythométriques + rapport détaillé complet)    | 35 000 XPF  |
| eval_n5 | Évaluation –  Techniciens, Maîtrises             | Évaluation de techniciens, agents de maîtrise, employés qualifiés (entretien structuré + tests psythométriques + rapport détaillé complet)        | 50 000 XPF  |
| eval_n6 | Évaluation – Managers opérationnels              | Évaluation de managers d'équipe, responsables de service, cadres (entretien structuré + tests psythométriques + rapport détaillé complet)         | 70 000 XPF  |
| eval_n7 | Évaluation – Cadres, responsables de département | Évaluation de cadres supérieurs, responsables de direction fonctionnelle (entretien structuré + tests psythométriques + rapport détaillé complet) | 90 000 XPF  |
| eval_n8 | Évaluation dirigeant / Executive                 | Évaluation de cadres dirigeants, directeurs généraux, membres de CODIR (entretien structuré + tests psythométriques + rapport détaillé complet)   | 110 000 XPF |

# Description entreprise
On crée l'entreprise à partir de son ridet (ridet est un identifiant légal unique). 
Quand il n'y a pas de ridet, on crée l'entreprise à partir de son nom
Si une entreprise existe déjà avec le ridet , alors on reprend l'existant
Si il n'y a pas de ridet, on regarde s'il existe une entreprise de nom proche qui existe (fuzzy search). On peut alors choisir une entreprise de la liste, ou en créer une nouvelle.
La description de l'entreprise est un champ de l'entreprise.
Les contacts associés à l'entreprise sont créés à partir des noms des dirigeants.

# to_email
to_email doit être complété manuellement dans la fiche de lead si l'entreprise n'est pas encore documentée. Il est choisi dans la liste des contacts associés à l'entreprise

# Classification des offres:

on utilise un appel à un LLM
- ministral-3:3b-cloud : https://ollama.com/library/ministral-3:3b-cloud
avec un prompt comme :
```text
Tu es un classificateur RH ultra-précis. Classifie l'offre d'emploi en UNE SEULE catégorie parmi les 5 suivantes :

- eval_n4 : Personnels d'exécution (opérateurs, ouvriers, employés)
- eval_n5 : Techniciens, agents de maîtrise, employés qualifiés
- eval_n6 : Managers opérationnels, responsables de service, cadres
- eval_n7 : Cadres supérieurs, responsables de département
- eval_n8 : Dirigeants / Executive (CODIR, DG)

Réponds EXCLUSIVEMENT avec un JSON valide et rien d'autre : {"code": "eval_nX"}
```

avec un appel direct à l'API d'Ollama, et "temperature": 0.0
