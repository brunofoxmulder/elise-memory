# PostgreSQL : état et travail restant

## Décision du 12 novembre 2026

Bruno a accepté de poursuivre avec SQLite pour le moment. Une vérification
ultérieure en lecture seule montre que l'application PostgreSQL with pgvector
0.1.0 est déjà installée et démarrée sur son Home Assistant. Mon évaluation
précédente surestimait donc le besoin d'un nouveau service : le coût de ce
service existe déjà. Cela ne démontre pas qu'une base soit configurée pour
Memory ni que le serveur Memory sache s'y connecter. La décision reste à
réexaminer avec ce nouveau fait ; aucune migration n'a été effectuée.

## Décision déjà prise pour la vectorisation

Le choix d'une API d'embeddings ou d'Ollama concerne la production des vecteurs.
Il ne choisit pas la base de données. La candidate actuelle conserve SQLite pour
les souvenirs et l'index documentaire. PostgreSQL n'est pas implémenté.

## Constats sur la révision amont utilisée

- La base des souvenirs utilise SQLite via `internal/dbutil/sqlite.go` et
  exécute des requêtes et migrations propres à SQLite, notamment des PRAGMA.
- L'index documentaire dispose d'une interface de stockage, mais
  l'implémentation en service est SQLite ; elle utilise notamment
  `INSERT OR REPLACE` et charge des vecteurs en mémoire pour le calcul.
- Un outil de migration devra aussi préserver les identifiants, métadonnées,
  dates, liens entre souvenirs et vecteurs existants, ainsi que les données de
  fonctionnement nécessaires. Les fichiers WAL de SQLite imposent une
  sauvegarde cohérente ; copier uniquement le fichier principal à chaud ne
  suffit pas comme méthode générale.

Sources :
- [Ouverture SQLite](https://github.com/ipiton/agent-memory-mcp/blob/dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b/internal/dbutil/sqlite.go)
- [Écriture des souvenirs](https://github.com/ipiton/agent-memory-mcp/blob/dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b/internal/memory/store_sql.go)
- [Stockage documentaire et vecteurs](https://github.com/ipiton/agent-memory-mcp/blob/dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b/internal/vectorstore/vectorstore.go)

## Conséquence

Ajouter une URL PostgreSQL dans l'application ne suffirait pas. Il faut
développer et valider un stockage compatible pour les souvenirs et, si retenu,
pour l'index documentaire, avec les transactions, migrations et recherches
correspondantes. Un remplacement du serveur MCP par un autre projet changerait
potentiellement les outils et comportements ; ce n'est pas une migration
transparente.

## Travail à réaliser avant toute bascule

1. Inventorier les tables, opérations, index et états de maintenance réellement
   utilisés par la révision épinglée ; définir un contrat de compatibilité MCP.
2. Développer le stockage PostgreSQL et les migrations nécessaires, sans retirer
   SQLite ni changer les outils disponibles aux clients.
3. Préparer un import de copie SQLite vers une base PostgreSQL isolée, vérifier
   les identifiants, champs, liens, compteurs et vecteurs, ainsi que le retour
   arrière. Évaluer séparément la nécessité et la compatibilité de pgvector.
4. Vérifier les sauvegardes et restaurations des deux stockages et mesurer
   les ressources sur le matériel cible avant une éventuelle décision.

Aucune migration n'a été effectuée. PostgreSQL with pgvector 0.1.0 est déjà
présent et démarré sur l'installation observée. La configuration
actuelle ne doit pas être présentée comme compatible PostgreSQL.
