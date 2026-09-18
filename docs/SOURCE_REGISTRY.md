# Registre de compilation canonique

Ce registre fixe le périmètre minimal de la première compilation `house`. Une source non listée ici n'entre pas automatiquement dans Memory.

| Source | Données compilées | Filtre | Données volontairement exclues |
|---|---|---|---|
| Home Assistant / Référentiel métier | fonction, entity_id, type, valeur métier, règle, matériel, criticité, commentaire | ligne non vide + source officielle renseignée | état HA courant |
| 00_Index / 09_Relations fonctionnelles | source, relation, cible, rôle, confiance | statut validé **et actif** | relations remplacées/inactives |
| Home Assistant / Mémoire IA | connaissance, domaine, preuves, confiance | statut commençant par Validé/Validée | hypothèses et connaissances à vérifier |

Les automatisations, le Référentiel HA exhaustif et les scripts seront ajoutés ensuite comme enrichissements, avec tests de filtrage propres à leur taxonomie. Ils ne sont pas aspirés en bloc.

## Règles fail-closed

- un en-tête obligatoire manquant bloque la compilation de la source ;
- les lignes vides sont ignorées ;
- aucun état instantané du Référentiel HA n'est compilé ;
- aucun YAML/code brut n'est compilé ;
- une nouvelle source doit avoir un test de pertinence et un test de dérive de schéma avant activation.
