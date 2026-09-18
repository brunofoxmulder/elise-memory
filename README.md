# Élise Memory

Mémoire locale déterministe pour le projet Maison Cognitive.

## Statut

Prototype isolé — aucune écriture dans Home Assistant ou Google Drive.

## Principes

- une seule application ;
- mémoire `house` structurée en couches **canonique** et **REX** ;
- mémoire `temporal` pour le contexte courant ;
- persistance locale SQLite sous `/data`;
- API HTTP locale et minimale ;
- aucune dépendance à un LLM ;
- Home Assistant reste la vérité du temps réel ;
- Google Drive reste le jumeau numérique documentaire canonique ;
- provenance, validation et historique de supersession conservés.

La base locale n'est pas une copie exhaustive des Sheets : elle compile seulement les connaissances utiles à la compréhension de la maison. Les historiques, tests, archives, YAML/code bruts et données de mesure ne sont pas injectés par défaut.

Voir `docs/HOUSE_KNOWLEDGE.md` pour les sources retenues, les exclusions, le REX et les garanties prévues pour la synchronisation nocturne.

Le raccordement à Élise Live, le déploiement Home Assistant et toute promotion REX vers Google Drive restent des étapes séparées soumises à validation explicite.


## Préparation du déploiement dev8

Le déploiement terrain est préparé sur la branche `dev8-deployment-package` sans modifier Home Assistant. La première mise en service doit conserver `ELISE_MEMORY_SYNC_ENABLED=false`, utiliser `/data/elise_memory.sqlite3` comme base persistante et valider d'abord les endpoints locaux `/health` et `/v1/sync/health`. Les identifiants Google ne sont ajoutés qu'après validation du démarrage isolé. Le retour arrière consiste à arrêter le service ; Élise Live et Home Assistant restent alors inchangés.
