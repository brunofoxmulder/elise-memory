# Contrat de mémoire pour Élise Live

## Rôle

Élise Memory fournit à l'agent un contexte consultatif, borné et sourcé. Elle ne
commande aucun équipement et ne remplace jamais l'état courant de Home Assistant.

Deux mémoires sont exposées :

- `house` : fonctionnement stable et validé de la maison ;
- `conversation` : éléments explicitement retenus d'un échange, avec provenance.

La couche `temporal` reste réservée aux faits à durée de validité explicite.

## Frontières obligatoires

1. Une commande est résolue et exécutée uniquement par les outils Home Assistant.
2. Avant une action, l'état et la cible actuels viennent de Home Assistant.
3. Une ambiguïté ne doit jamais être tranchée par la mémoire : l'agent demande une
   précision.
4. Une question causale (« pourquoi… ») est routée vers Investigator. La mémoire
   ne produit pas de diagnostic causal.
5. Les résultats mémoire ne sont jamais injectés en bloc dans le prompt permanent.
   Le modèle appelle l'outil seulement en cas de doute, d'hésitation ou de besoin
   de contexte.

## Point d'intégration

Le serveur expose `POST /v1/agent/query`. La future intégration Home Assistant doit
l'enregistrer comme API LLM distincte et sélectionnable. Élise Live sait déjà
fusionner les API LLM choisies par l'utilisateur ; aucune modification de sa boucle
audio ou de sa conservation de session n'est requise.

Réponse garantie :

- `advice_only=true` ;
- `may_execute=false` ;
- `route=memory` avec faits, relations et souvenirs sourcés ; ou
- `route=investigator` sans résultat mémoire pour une question causale.

Ce contrat ne constitue pas une validation de déploiement. L'intégration, les
droits réseau et la recette vocale doivent être testés isolément avant installation.
