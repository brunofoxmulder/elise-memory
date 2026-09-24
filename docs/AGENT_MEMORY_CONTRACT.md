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

Le serveur expose `POST /v1/agent/query` pour les tests et un serveur MCP Streamable
HTTP sur `/mcp`. L'intégration MCP officielle de Home Assistant peut enregistrer ce
serveur comme API LLM distincte et sélectionnable. Élise Live sait déjà fusionner
les API LLM choisies par l'utilisateur ; aucune modification de sa boucle audio ou
de sa conservation de session n'est requise.

Le serveur MCP ne publie qu'un outil : `consult_elise_memory`. L'outil est en lecture
seule et retourne le même contrat borné que l'API HTTP. Le port hôte de l'app n'est
plus exposé par défaut ; une éventuelle exposition doit être décidée et validée lors
de la recette réseau.

L'app annonce également le service `mcp` par le mécanisme de découverte Supervisor.
L'URL annoncée est construite à partir du nom interne réel du conteneur :
`http://<hostname>:8099/mcp/`. Home Assistant peut ainsi proposer l'intégration MCP
sans port LAN, adresse IP fixe ni intégration personnalisée. L'utilisateur doit
toujours confirmer l'ajout dans Home Assistant ; l'annonce seule ne l'active pas.

La consultation MCP reste sans authentification : elle suppose un réseau interne
de confiance. Un port hôte désactivé n'isole pas l'app des autres conteneurs.
La protection DNS rebinding accepte uniquement loopback et le nom réel du conteneur,
sans autoriser d'origine navigateur. L'intégration réelle reste à tester sur HAOS.

Les quatre routes HTTP mutantes (sync, création mémoire, capture conversationnelle,
confirmation de salutation) sont désormais désactivées par défaut (HTTP 503).
Un appel administratif exige `ELISE_MEMORY_ADMIN_TOKEN` d'au moins 32 caractères
et le même secret dans `Authorization: Bearer …` (sinon HTTP 401).
Ne jamais réutiliser le jeton Supervisor. Aucun secret n'est fourni aux outils MCP.
Le provisionnement de ce secret dans HAOS n'est pas inclus dans ce correctif.

Le champ `user_confirmed` est une déclaration du client authentifié, pas une preuve
technique du consentement de Bruno. Le filtrage des secrets, l'isolation des souvenirs
par utilisateur et la recette fonctionnelle du corpus restent à valider avant déploiement.

Réponse garantie :

- `advice_only=true` ;
- `may_execute=false` ;
- `route=memory` avec faits, relations et souvenirs sourcés ; ou
- `route=investigator` sans résultat mémoire pour une question causale.

Ce contrat ne constitue pas une validation de déploiement. L'intégration, les
droits réseau et la recette vocale doivent être testés isolément avant installation.
