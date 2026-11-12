# Raccordement préparatoire d'Hermès à Agent Memory MCP

Statut : proposition de configuration, non appliquée et non testée sur
l'installation HAOS réelle. Branche candidate Memory 0.1.2-dev.1.

## But

Hermès et les agents Assist peuvent utiliser le même serveur et la même base
de souvenirs, indépendamment de leurs modèles conversationnels. Bruno confirme
qu'Hermès doit pouvoir consulter, créer, modifier et supprimer les souvenirs.
Assist peut les consulter et également les alimenter selon les instructions
retenues par Bruno. L'accès d'Hermès à
Home Assistant lui-même reste en lecture seule.

La mémoire native et les profils d'Hermès ne deviennent pas automatiquement
la mémoire partagée : les outils MCP doivent être configurés et utilisés.

## Faits vérifiés et limites

- Le code et la documentation amont d'Hermès v0.23.0 prévoient des serveurs
  MCP HTTP dans `mcp_servers` et un filtrage par nom d'outil.
- L'application Hermès présente dans le dépôt `elise-hermes-haos` embarque
  v0.23.0, mais son manifeste `main` indique 0.1.0. L'installation de Bruno
  est rapportée en 0.1.2 : l'image et le mécanisme de configuration effectifs
  de cette installation restent à vérifier.
- Les observations rapportées montrent qu'Assist retrouve des souvenirs ; elles
  ne démontrent pas à elles seules une écriture par Hermès suivie d'une lecture
  par Assist dans des sessions indépendantes.
- Le serveur Memory en service a été observé sur `http://172.30.32.1:18080/mcp`
  depuis l'environnement de diagnostic. Cela ne prouve pas que cette adresse
  est accessible depuis le conteneur Hermès ni qu'elle restera stable.
- Le serveur actuel accepte des appels sans authentification. Restreindre les
  outils affichés par Hermès ne sécurise pas le serveur sur le réseau.

Sources : [Hermès v0.23.0 — configuration MCP](https://github.com/NousResearch/hermes-agent/blob/v0.23.0/website/docs/user-guide/features/mcp.md),
[dépôt de l'application Hermès](https://github.com/brunofoxmulder/elise-hermes-haos),
et diagnostic fourni dans la séance Memory.

## Exemple de configuration à examiner

Extrait indicatif de `~/.hermes/config.yaml`, à fusionner avec les entrées
existantes après vérification du profil et du chemin réellement utilisés.
`enabled: false` empêche la connexion : cet exemple est volontairement inactif.

```yaml
mcp_servers:
  agent_memory:
    enabled: false
    url: "http://172.30.32.1:18080/mcp"
    tools:
      include: [memory, search]
      resources: false
      prompts: false
```

L'adresse est celle observée lors du diagnostic et doit être confirmée depuis
Hermès. La liste présente la mémoire et la recherche documentaire ; `memory`
regroupe lecture, création, modification et suppression, conformément au choix
de Bruno. Ce filtrage ne protège pas le serveur des autres clients réseau.

## Conditions préalables à la mise en service

1. Reconstituer la configuration et les accès réellement en place, sans
   afficher les secrets ; vérifier les sauvegardes et la possibilité de retour
   arrière.
2. Résoudre l'accès réseau non authentifié et vérifier les permissions effectives
   des clients. Maintenir l'accès HA d'Hermès en lecture seule ; les permissions
   de gestion de Memory sont distinctes.
3. Valider la version Hermès, son profil actif, l'adresse joignable et le
   mécanisme d'enregistrement des paramètres MCP ; préserver les autres
   connexions existantes.
4. Valider explicitement avec Bruno toute modification opérationnelle dans
   la séance Maison Cognitive.

## Recette ciblée après validation

Sur une instance de test isolée avec données fictives, puis seulement si
autorisé sur l'installation réelle :

1. Observer la découverte des outils sans demander de modification de données.
2. Faire enregistrer par Hermès une information fictive clairement identifiée.
3. Démarrer une nouvelle conversation Assist et demander cette information ;
   vérifier le contenu restitué et, si possible, l'appel effectif.
4. Tester le sens inverse : écriture Assist, puis lecture Hermès dans une
   nouvelle conversation. Garder trace des résultats et des erreurs.
5. Vérifier que les autres outils MCP et la lecture seule HA restent utilisables.

La modification et la suppression peuvent être vérifiées en bac à sable sur
un souvenir fictif clairement identifié, sans toucher aux données de production.
La disponibilité du RAG et des embeddings dépend de leur configuration propre ;
un échec réseau ou de modèle ne doit pas être interprété comme un souvenir
absent. Les appels de rappel peuvent modifier des statistiques d'accès.

## Ce qui reste à construire ou vérifier

Authentification et confidentialité réseau,
raccordement effectif d'Hermès et d'Assist, règles de qualité des souvenirs,
indexation documentaire réelle, sauvegarde et restauration HAOS. PostgreSQL
n'est pas implémenté dans la candidate actuelle.


## Étude de sécurisation — 12 novembre 2026

Le code amont de Memory à la révision utilisée sait vérifier un jeton HTTP
`MCP_HTTP_AUTH_TOKEN`. Le code d'Hermès v0.23.0 documente les en-têtes
`Authorization` pour un serveur MCP distant. En revanche, la configuration
du client MCP de Home Assistant examinée dans ce chantier ne proposait pas de
champ pour saisir directement ce jeton. Ce point dépend de la version et du
client : il doit être revérifié avant toute mise en service.

| Solution | Intérêt | Limite à lever |
| --- | --- | --- |
| Jeton unique sur Memory | Protège le serveur contre les appels sans jeton ; Hermès peut être configuré avec un en-tête | Assist pourrait perdre l'accès ; un jeton sur HTTP ne chiffre ni jeton ni contenu |
| Réseau interne sans port publié | Réduit l'exposition au réseau local si l'isolement fonctionne | Ne garantit ni authentification ni séparation entre applications internes ; adresses et accès HA/Hermès à tester |
| Passerelle d'authentification compatible avec les deux clients | Permet de conserver un point commun contrôlé | Compatibilité du client HA, complexité et maintenance non démontrées |

La piste du réseau interne mérite d'être examinée avant d'ajouter un autre
service : le manifeste actuel utilise `host_network: true` et le port 18080.
Un changement de réseau peut rompre les URL utilisées par Assist, Hermès ou
un autre client ; il ne doit pas être appliqué sans inventaire, recette et
retour arrière. Le serveur resterait accessible aux clients du réseau interne
autorisés par la configuration réseau, sans identité individuelle garantie.

Ne pas activer un jeton global, retirer le port ou modifier une connexion en
production avant d'avoir confirmé le chemin des deux clients et obtenu la
validation explicite de Bruno.

Sources : [contrôle HTTP de Memory épinglé](https://github.com/ipiton/agent-memory-mcp/blob/dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b/internal/server/http_security.go),
[configuration MCP Hermès v0.23.0](https://github.com/NousResearch/hermes-agent/blob/v0.23.0/website/docs/user-guide/features/mcp.md),
[documentation Home Assistant sur les applications](https://developers.home-assistant.io/docs/apps/).
