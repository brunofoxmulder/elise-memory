# Élise Memory

Mémoire locale déterministe pour Home Assistant.

## Sécurité et confidentialité

- aucun identifiant de classeur Google n'est embarqué dans le code ;
- aucun compte de service, jeton ou secret Google n'est stocké dans le dépôt ;
- les identifiants de classeurs sont fournis uniquement par la configuration privée de l'App ;
- le compte de service est lu depuis le fichier local `/config/google-service-account.json` ;
- l'accès Google utilise uniquement l'API Sheets en lecture seule ;
- les états de santé n'exposent ni chemin de secret ni identifiant de classeur.

## Fonctionnement

- mémoire `house` structurée en couches **canonique** et **REX** ;
- mémoire `temporal` pour le contexte courant ;
- persistance SQLite sous `/data` ;
- API HTTP locale ;
- aucune dépendance à un LLM ;
- Home Assistant reste la vérité du temps réel ;
- la synchronisation Google vers SQLite est atomique : toutes les sources requises sont lues et compilées avant publication.

## Synchronisation Google

La synchronisation est désactivée par défaut. L'App monte son dossier `addon_config`
explicitement sur `/config` et attend un fichier nommé
`google-service-account.json`.

Si la synchronisation est activée mais que le fichier de credentials, les IDs de
classeurs ou les credentials eux-mêmes sont invalides, **l'App reste démarrée**.
La synchronisation passe en état non prêt/échec et aucune publication canonique
partielle n'est effectuée.

Le raccordement à un agent conversationnel/Assist est une étape séparée et ne
doit être activé qu'après validation terrain de la chaîne Google → SQLite.
