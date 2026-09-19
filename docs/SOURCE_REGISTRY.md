# Registre de compilation canonique

## V1 actuellement déployée

La branche `main` / dev.13 conserve le périmètre V1 : compilation plate de connaissances canoniques et recherche locale SQLite. Ce registre historique reste utile pour comprendre la version installée, mais il ne constitue plus la cible fonctionnelle pour les questions sur le fonctionnement des automatisations.

## Cible V2 — branche expérimentale dev16

L'audit Drive du 19/09/2026 a montré qu'une simple recherche plein texte dans des connaissances aplaties n'est pas suffisante. La cible V2 sépare l'identité actuelle, le comportement, les relations, le sens métier et l'historique.

| Type de fait | Source prioritaire | Usage V2 | Garde-fou |
|---|---|---|---|
| existence / identité technique actuelle | Automatisations / Référentiel HA puis, à terme, lecture HA live read-only | entity_id, domaine, nom actuel, présence de l'automation | une ligne documentaire seule ne prouve pas l'existence actuelle |
| état courant | Home Assistant live read-only | état réellement courant | le snapshot Drive n'est qu'un export daté |
| comportement d'une automation | Automatisations / YAML Production réconcilié avec l'automation actuelle | triggers, guards, waits, actions, effets, cibles | Test et Production -1 exclus du comportement courant |
| dépendances documentaires | Automatisations / Objets Home Assistant | enrichissement USES | une dépendance ne devient jamais automatiquement TRIGGER/GUARD/ACTION |
| relation structurante validée | 00_Index / 09_Relations fonctionnelles | corroboration, rôle, preuve, confiance | R8 est ciblée et non exhaustive |
| sens métier | Home Assistant / Référentiel métier | fonction, règle attendue, criticité | la sémantique métier est séparée de son binding entity_id courant |
| scripts | Scripts - Maison Cognitive / Scripts Pyscript | rôle, service, entrées/sorties | le code brut reste hors contexte conversationnel |
| connaissance durable | Home Assistant / Mémoire IA | connaissance explicitement validée | ne remplace jamais un fait HA courant |
| histoire / décisions | Journal, Index, RDA, historiques | expliquer une évolution ou une décision | ne doit jamais être promue implicitement en état actuel |

### Réconciliation Automatisations

Une ligne `Automatisations` peut alimenter le graphe opérationnel uniquement si sa Production est réconciliée avec une automation du Référentiel HA courant par nom/alias normalisé exact. Le fuzzy matching ne décide jamais qu'une automation existe.

Par défaut, seules les automations réconciliées et actuellement `on` entrent dans le graphe opérationnel. Une automation `off` reste connaissable comme objet actuel désactivé, mais ne doit pas être présentée comme une règle active.

### Compilation du YAML Production

Le YAML Production est lu localement par un parseur déterministe. Le YAML brut n'est pas envoyé au LLM et n'est pas renvoyé comme contexte conversationnel. Il est transformé en relations atomiques telles que :

- entité → `TRIGGERS` → automation ;
- entité → `GUARDS` → automation ;
- entité → `WAITS_FOR` → automation ;
- automation → `ACTS_ON` → entité ;
- automation → `CALLS_AUTOMATION` → automation ;
- automation → `BARRIER` → temporisation.

Les références internes de registre Home Assistant de 32 caractères sont conservées sous forme `registry_ref` / `device_ref` et ne sont jamais converties par ressemblance de nom. Une résolution exige une preuve read-only du registre HA ou une source officielle explicite.

### Référentiel métier

Le sens métier et la liaison technique sont deux faits distincts. Par exemple, une ancienne ligne métier peut encore décrire correctement le rôle « volet salon » tout en pointant vers un ancien `entity_id`. Dans ce cas, la règle métier reste disponible comme sémantique, mais son binding est marqué périmé et n'entre pas dans le contexte de l'entité actuelle.

### Recherche opérationnelle

Pour une question sur une lampe, une prise, un volet ou une charge :

1. résoudre d'abord l'objet vers l'identité HA actuelle ;
2. traverser les relations techniques directes du graphe ;
3. filtrer par l'effet demandé lorsque la question dit explicitement allumer/éteindre/ouvrir/fermer ;
4. retourner toutes les automations actives qui agissent réellement sur la cible ;
5. enrichir ensuite seulement avec R8, métier, scripts ou connaissance validée ;
6. garder les simples mentions textuelles et l'historique hors du classement opérationnel primaire.

## Audit Drive de référence — 19/09/2026

Constats de lecture seule utilisés pour la conception V2 :
- 114 entités `automation` dans le Référentiel HA courant : 107 ON et 7 OFF ;
- 117 lignes Automatisations comportent une Production ;
- 106 Productions ont été réconciliées avec une automation actuellement ON ;
- 5 Productions correspondent à une automation actuellement OFF ;
- 6 Productions restent documentées sans correspondance actuelle certaine ;
- une automation actuellement ON ne trouve pas de ligne documentaire exacte ;
- 97 des 106 automations actives réconciliées ont au moins une dépendance dans `Objets Home Assistant` ;
- 16 Productions actives contiennent au moins une référence entity_id interne opaque de 32 caractères ;
- le Référentiel métier contient deux bindings directs d'anciens volets absents de l'inventaire courant, ce qui confirme la nécessité de séparer sémantique et binding.

Ces chiffres décrivent les sources Drive auditées ; ils ne valent pas validation terrain exhaustive des automatismes.

## Règles fail-closed V2

- un en-tête obligatoire manquant bloque la compilation de la source concernée ;
- une ligne documentaire non réconciliée ne devient pas une automation active ;
- une référence de registre opaque n'est jamais devinée ;
- une contradiction entre une source documentaire et l'identité HA actuelle reste visible ;
- le statut historique ne peut pas gagner sur un fait courant ;
- le graphe opérationnel ne déduit jamais une action depuis une simple mention textuelle ;
- les sources historiques restent disponibles pour les questions historiques, pas pour établir l'état courant ;
- la V2 reste hors du chemin terrain tant que le benchmark et les tests de non-régression ne sont pas consolidés.
