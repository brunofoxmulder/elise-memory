# Élise Memory — moteur V2 orienté objets et relations

## Pourquoi cette refonte existe

Les essais terrain ont montré que la recherche House Memory V1 ne peut pas être corrigée proprement par un simple ranking. Le moteur V1 met plusieurs sources Drive dans une même table, effectue une recherche plein texte avec des OR et retourne des lignes. Cela mélange l'identité actuelle Home Assistant, le fonctionnement YAML, la sémantique métier, les relations validées et l'historique.

La documentation Maison Cognitive donne déjà la règle correcte : Home Assistant reste la source de vérité sur la maison actuelle ; les contextes doivent être construits de façon déterministe ; la préséance/péremption documentaire (R6) et les relations prouvées (R8) doivent rester explicites.

Cette branche est un prototype **hors terrain**. Elle ne modifie ni Home Assistant ni l'API utilisée par Élise Live.

## Audit Drive du 19/09/2026

Lecture des sources vivantes officielles :
- `Automatisations / Référentiel HA`
- `Automatisations / Automatisations`
- `Automatisations / Objets Home Assistant`
- `Home Assistant / Référentiel métier`
- `00_Index / 09_Relations fonctionnelles`
- `Scripts - Maison Cognitive / Scripts Pyscript`
- décisions/méthodes/procédures de l'Index pour la gouvernance.

Constats mesurés pendant l'audit :
- 114 entités `automation` dans le Référentiel HA courant, dont 107 ON et 7 OFF ;
- 117 lignes Automatisations comportent une Production ;
- 106 Productions ont été réconciliées avec une automation actuellement ON ;
- 5 Productions correspondent à une automation actuellement OFF ;
- 6 Productions restent documentées alors qu'aucune automation courante ne correspond exactement ;
- 3 automations courantes ne trouvent pas de ligne documentaire exacte, dont une active ;
- 97 des 106 automations actives réconciliées disposent d'au moins une dépendance dans `Objets Home Assistant` ;
- certaines device actions utilisent des identifiants internes opaques de registre au lieu d'un `entity_id` stable. Elles doivent rester non résolues tant qu'une preuve de mapping n'existe pas.

Ces chiffres sont des constats de l'audit Drive, pas une validation terrain exhaustive des 107 automations.

## Principe : le type de fait choisit la source prioritaire

Il n'existe pas une source universellement prioritaire.

| Type de fait | Source prioritaire | Rôle des autres sources |
|---|---|---|
| existence d'un objet/automation | Référentiel HA courant / HA live | documentation = contexte seulement |
| état courant | Home Assistant live | snapshot Drive = dernier export, jamais temps réel garanti |
| comportement d'une automation | YAML Production réconcilié avec l'automation courante | descriptif/métier = explication |
| relation technique | relation extraite du YAML Production | R8 et Objets HA = corroboration/enrichissement |
| sens métier | Référentiel métier | YAML = mise en œuvre |
| connaissance durable | Mémoire IA validée | ne remplace jamais un fait HA courant |
| histoire/décision | Journal, Décisions, RDA | ne doit pas devenir l'état actuel |

Une source moins autoritaire peut compléter une source plus autoritaire, jamais la contredire silencieusement.

## Pipeline V2

### 1. Identité actuelle

Construire les objets depuis le Référentiel HA courant (et, plus tard, une lecture HA live read-only pour la fraîcheur). Chaque objet porte :
- `entity_id` stable courant ;
- domaine ;
- nom visible ;
- état observé uniquement comme information de snapshot, pas comme vérité temps réel.

### 2. Réconciliation des automations

Une ligne de `Automatisations` devient opérationnelle seulement si :
1. sa Production existe ;
2. son nom ou l'alias YAML correspond exactement, après normalisation, à une automation présente dans le Référentiel HA courant ;
3. pour les réponses opérationnelles par défaut, cette automation est ON.

Pas de fuzzy matching pour décider qu'une automation existe. Une ligne Drive non réconciliée reste documentaire/historique.

### 3. Compiler le YAML en relations atomiques

Le YAML n'est pas envoyé au LLM. Il est parsé localement et transformé en graphe :

- `entité -> TRIGGERS -> automation`
- `entité -> GUARDS -> automation`
- `entité -> WAITS_FOR -> automation`
- `automation -> ACTS_ON -> entité`
- `automation -> CALLS_AUTOMATION -> automation`
- `automation -> BARRIER -> délai`

Le détail de l'arête conserve le service, l'effet, le seuil, la durée et les paramètres utiles.

### 4. Résoudre d'abord l'objet demandé

Une question telle que « qu'est-ce qui allume la lampe de la salle de bain ? » doit d'abord résoudre `Lampe salle de bain` vers l'entité HA actuelle. Ensuite seulement le moteur remonte les arêtes `ACTS_ON`.

Les mentions textuelles de « salle de bain » dans une notification, une description ou un Echo ne participent pas au classement opérationnel.

### 5. Retourner toutes les chaînes directes pertinentes

Une entité peut légitimement être commandée par plusieurs automations. Le moteur ne doit pas forcer un « gagnant » unique.

Pour la lampe d'entrée, si deux automations actives font réellement un `light.turn_on` sur la même lampe, les deux doivent être retournées avec leurs déclencheurs et conditions.

### 6. Intention de l'action

Lorsque la question précise « ouvre », « ferme », « allume » ou « éteint », le service/effect extrait du YAML sert au classement :
- turn_on / turn_off ;
- open / close / set_position ;
- lock / unlock ;
- autres effets déterministes.

Cela permet à un même volet d'avoir plusieurs chaînes sans confondre ouverture et fermeture.

## Imbrication des sources Drive

Une réponse opérationnelle V2 est assemblée, pas choisie dans une ligne :

1. **Référentiel HA** : identité et existence courantes ;
2. **Production réconciliée** : comportement déterministe ;
3. **Objets Home Assistant** : dépendances et enrichissements ;
4. **R8** : relations structurantes validées, avec preuve et statut ;
5. **Référentiel métier** : sens, règle attendue et criticité ;
6. **Scripts Pyscript** : rôle/service/dépendances lorsqu'une automation appelle un script ;
7. **Mémoire IA validée** : connaissance durable complémentaire ;
8. **Décisions / Journal / RDA** : explication historique lorsque la question le demande.

L'historique n'entre jamais automatiquement dans une réponse sur l'état actuel.

## Cas difficile : device actions

Plusieurs automations de charge utilisent encore dans le YAML des références internes de registre de 32 caractères. Le Drive courant ne fournit pas toujours la correspondance certaine entre cette référence et l'entity_id stable (ex. prise physique).

Le moteur V2 doit donc :
- conserver `registry_ref:<id>` ;
- ne jamais inventer le switch correspondant ;
- chercher une preuve de résolution dans une future couche read-only du registre HA ou une source officielle explicite ;
- seulement après résolution, créer l'arête vers le vrai `switch.xxx`.

C'est une différence essentielle avec une recherche sémantique : une bonne ressemblance de nom n'est pas une preuve d'identité.

## Statut de la branche

Le prototype `engine_v2.py` et ses tests sont volontairement non raccordés à `/v1/knowledge/search`. Le but est de stabiliser le contrat du moteur et les régressions avant de toucher au chemin utilisé par Élise Live.

Aucun redémarrage Home Assistant n'est requis pour cette phase.


## Couverture réelle du YAML Drive — audit du 19/09/2026

L'audit a été refait sur les 106 automatisations dont la Production est réconciliée avec une automation actuellement ON dans le Référentiel HA.

Constructions observées :
- 26 automations utilisent `choose` ;
- 6 utilisent `wait_for_trigger` et 1 utilise `wait_template` ;
- 15 utilisent des `delay` ;
- 3 utilisent `if/then/else` ;
- 1 utilise `repeat` ;
- 23 contiennent au moins une condition template ;
- 11 contiennent un trigger device ;
- 1 contient une condition temporelle explicite ;
- 1 contient une action `stop`.

Le moteur V2 doit donc préserver non seulement les cibles, mais aussi l'ordre local, la branche, les guards et les barrières temporelles. Les guards d'une branche `choose` ne doivent jamais être attribués aux actions d'une autre branche, et un wait situé après une action ne doit jamais être recyclé comme condition de cette action.

### Références internes Home Assistant

L'audit montre aussi que les actions/trigger de type device restent un point dur :
- 11 occurrences de trigger device, dont 5 utilisent un identifiant d'entité opaque de registre ;
- 18 actions device observées, toutes avec un identifiant d'entité opaque dans le YAML exporté.

Ces références sont conservées telles quelles dans le graphe. Elles ne sont résolues vers un `entity_id` courant que lorsqu'un binding explicite et prouvé est fourni. Une ressemblance de nom, un device_id voisin ou une ligne documentaire ne suffit jamais.

### Cas désormais explicitement couverts par tests

La suite de régression couvre maintenant :
- séparation des sources courantes, documentaires et historiques ;
- réconciliation fail-closed des automations ;
- questions cible → automations actives ;
- questions source/trigger → automations → effets ;
- plusieurs automations légitimes sur une même cible ;
- ouverture/fermeture distinctes sur un même volet ;
- `choose`, `if/then/else`, `wait_for_trigger`, `wait_template`, délais et stop ;
- portée locale des guards de branche ;
- ordre des waits par rapport aux actions ;
- conditions temporelles ;
- conditions template, y compris les templates dynamiques sans entity_id statique ;
- références `states.sensor.xxx` en syntaxe pointée ;
- steps désactivés via `enabled: false` ;
- appels script, Pyscript, automation et services sans cible explicite ;
- résolution d'objet en français pour lampes, volets, serrures et charges ;
- résolution explicite des références de registre sans guessing.

Cette couverture reste une validation de code. Elle ne remplace ni la validation terrain Home Assistant, ni la résolution des références opaques par le registre HA réel.
