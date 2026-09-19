# Élise Memory

Application Home Assistant de mémoire locale déterministe.

## Source unique

Le code réellement livré à Home Assistant se trouve dans `elise-memory/app/`.
La CI installe et teste **ce même paquet**, puis construit l'image Home Assistant
et lance des tests HTTP sur le conteneur final.

## Confidentialité

- aucun ID de Google Sheet n'est embarqué dans le code ;
- aucun credential, jeton ou secret Google n'est stocké dans le dépôt ;
- les IDs de classeurs sont des options privées de l'App ;
- le compte de service est lu depuis `/config/google-service-account.json` ;
- Google Sheets est utilisé en lecture seule ;
- l'API de santé n'expose ni ID, ni secret, ni chemin utilisateur.

## Robustesse

Une configuration Google absente ou invalide ne doit jamais empêcher l'App de
démarrer. La synchronisation devient simplement `not_ready` et la base
canonique existante reste intacte.

## Contrat dev.17

Élise Memory reste une mémoire d'agent légère. Elle fournit un contexte borné, la mémoire temporelle, les connaissances durables et une aide de résolution d'objet. Elle n'exécute aucune commande Home Assistant et ne reconstruit pas la causalité d'un événement : ce rôle appartient à Élise Investigator.

### Véracité

- l'identité et l'état techniques actuels proviennent de Home Assistant en lecture seule ;
- les connaissances canoniques et le REX validé restent séparés et traçables ;
- une connaissance `candidate` n'est jamais retournée comme fait à l'agent ;
- une résolution ambiguë reste explicitement non résolue ;
- une absence de preuve n'est jamais transformée en preuve.

### Usage agent

- `GET /v1/knowledge/search?q=...` : petit contexte durable pertinent ;
- `POST /v1/context` : contexte demandé explicitement par clés ;
- `POST /v1/conversation/open` : micro-contexte d'ouverture + mémoire explicitement demandée ;
- `GET /v1/resolve/entity?q=...` : aide à identifier une cible parmi les entités HA actuellement présentes ;
- `GET /v1/session/open` et commit du greeting : mémoire temporelle réveil/session.

L'agent utilise Home Assistant directement lorsqu'il connaît déjà la cible. Il consulte Memory lorsqu'il a besoin de contexte ou hésite sur l'objet. Les questions de causalité d'un événement réel sont routées vers Investigator.
