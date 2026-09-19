# Politique de mémoire conversationnelle

## Principe

Élise Memory ne conserve pas automatiquement une conversation et ne stocke pas
de transcription audio ou textuelle brute. Une mémoire conversationnelle est un
résumé court, explicitement confirmé par Bruno, accompagné de la provenance du
tour de conversation.

## Éléments admissibles

- une préférence explicitement formulée ;
- un fait personnel fourni par Bruno ;
- un contexte durable concernant le foyer ;
- un engagement ou une décision à reprendre ultérieurement.

## Éléments interdits

- mots de passe, jetons, clés ou autres secrets ;
- transcription brute ou enregistrement audio ;
- hypothèse, déduction ou interprétation non confirmée ;
- cible ou commande Home Assistant utilisée comme raccourci d'exécution ;
- conclusion causale relevant d'Investigator ;
- état technique volatil qui doit être relu dans Home Assistant.

## Contrat d'écriture

L'outil MCP `consult_elise_memory` reste strictement en lecture seule. L'écriture
utilise séparément `POST /v1/conversation/memories` et exige :

- `conversation_id` et `turn_id` pour la provenance ;
- une catégorie fermée (`preference`, `personal_fact`, `household_context` ou
  `commitment`) ;
- un sujet et un résumé borné à 1000 caractères ;
- `user_confirmed=true`.

L'ancien endpoint générique refuse le type `conversation`. Aucun appel automatique
de cette voie d'écriture n'est inclus dans ce candidat.
