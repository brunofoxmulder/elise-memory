# Déploiement terrain dev8

Ce paquet prépare Élise Memory comme service isolé. Il ne modifie pas Home Assistant et n'active pas la synchronisation Google par défaut.

## Invariants

- image Python 3.12 minimale ;
- SQLite persistante dans `/data/elise_memory.sqlite3` ;
- port HTTP interne 8099 ;
- `ELISE_MEMORY_SYNC_ENABLED=false` par défaut ;
- aucun secret dans l'image ou le dépôt ;
- aucune écriture Home Assistant ou Google Drive.

## Première mise en service

1. Construire l'image depuis le commit validé.
2. Monter un volume persistant sur `/data`.
3. Démarrer sans identifiants Google et avec la synchronisation désactivée.
4. Vérifier `GET /health` puis `GET /v1/sync/health`.
5. Ne configurer le lecteur Google qu'après validation de ce démarrage isolé.

## Retour arrière

Arrêter le service et conserver le volume `/data`. Aucun changement HA n'est nécessaire pour revenir à l'état antérieur puisque dev8 n'est pas encore raccordée à Élise Live. La base SQLite peut être sauvegardée avant toute activation de synchronisation.
