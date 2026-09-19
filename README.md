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
