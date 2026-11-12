# Raccordement préparatoire d'Hermès à Agent Memory MCP

Statut : proposition de configuration, non appliquée et non testée sur
l'installation HAOS réelle. Branche candidate Memory 0.1.2-dev.1.

## But

Bruno confirme qu'Hermès est chargé de lire et digérer les documents, puis de
préparer et gérer les souvenirs structurés dans Memory, avec leur source. Les
formats qu'Hermès sait traiter et son accès aux documents restent à vérifier.

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

## Passage de relais depuis Élise

Quand Bruno transmet à Hermès un document ou un texte préparé par Élise,
utiliser le modèle suivant après vérification de la connexion à Memory :

> Lis le contenu que je te transmets et relève les informations utiles à
> conserver. Pour chaque information, recherche d'abord dans Memory les
> souvenirs proches. Garde la source, la date du document lorsqu'elle est
> connue et distingue les faits confirmés des hypothèses ou points à vérifier.
> Crée les souvenirs manquants ; mets à jour les souvenirs existants quand la
> correction est justifiée par la source. Si les sources se contredisent ou si
> une information est ambiguë, conserve la trace des deux versions et
> indique-moi le point à éclaircir. Ne déduis pas qu'une information est fausse
> simplement parce qu'elle est absente du document. Ne supprime ni ne fusionne
> des souvenirs sur la seule base d'une ressemblance ; présente-moi les cas
> incertains. Signale les documents ou passages que tu n'as pas pu lire.
> Termine par un bilan des créations, mises à jour, cas incertains et erreurs.

Cette instruction organise le transfert demandé ; elle ne remplace pas les
autorisations techniques. Bruno autorise Hermès à modifier et supprimer des
souvenirs ; la prudence sur un transfert en masse évite de confondre une
ressemblance avec une preuve. Les demandes explicites ultérieures de Bruno
priment. Le texte transmis est une source datée, pas nécessairement une
représentation exhaustive ni toujours actuelle des souvenirs de ChatGPT.

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


## Variante réseau interne préparée — 12 novembre 2026

Le fichier `tests/proposition-reseau-interne.patch` est une proposition à
examiner séparément ; il n'est pas appliqué au manifeste de la candidate. Il
remplace le réseau hôte par le réseau interne et retire la publication du port.
Selon la documentation officielle Home Assistant, les applications du réseau
interne peuvent se joindre par leur nom DNS et le port de destination. Ce
mécanisme ne fournit pas d'identité ni de protection entre applications.

Pour le nom exact, utiliser l'identifiant complet réel de l'application tel
qu'affiché par Supervisor, en remplaçant les tirets bas par des tirets. Le
préfixe de dépôt dépend de l'installation et ne doit pas être deviné.

Points à vérifier sur un banc HAOS avant toute décision :

- Résolution du nom et accès MCP depuis le processus de Home Assistant Core et
  le profil d'Hermès, sur le port interne 18080 ; les noms et adresses actuels
  vers l'hôte ne conviendront pas nécessairement après la transition.
- Absence d'accès depuis le réseau domestique, en tenant compte des autres
  routes et relais éventuellement présents.
- Préservation des données, des outils Assist et des fonctions d'Hermès après
  bascule, puis retour à la configuration antérieure si nécessaire.
- Ollama : `127.0.0.1` désigne le conteneur Memory après cette bascule, et
  non l'hôte ou un autre conteneur. Si Ollama est ailleurs, son adresse
  joignable doit être configurée ; ne pas présumer qu'il est déjà installé.

Les essais Docker de la candidate précédente ne constituent pas un test du
réseau Supervisor ou de la variante ci-dessus. Le réseau interne réduit
l'exposition potentielle, mais toutes les applications capables de joindre le
service peuvent encore utiliser les droits exposés, y compris la suppression.

Sources : [réseau des applications](https://contributors.home-assistant.io/apps/guides/communication/),
[configuration réseau](https://contributors.home-assistant.io/apps/reference/configuration/).


## Lecture de documents par Hermès — examen du code v0.23.0

Le code amont de `read_file` prévoit l'extraction des fichiers DOCX et XLSX,
ainsi que des notebooks, sans convertisseur externe pour ces formats. Le
parcours PDF et d'autres formats dépend d'un composant optionnel ; la skill PDF
fournit aussi des méthodes d'extraction avec leurs propres dépendances. Leur
présence et leur fonctionnement dans l'image réellement installée ne sont pas
démontrés par la lecture du dépôt.

Limites observées dans le code : limite de 50 Mio pour les documents concernés,
limite XLSX de 5 000 lignes et 256 colonnes par feuille, et pagination ou
limitation possible des textes renvoyés. Un PDF scanné nécessite une solution
OCR appropriée. La lecture de tous les éléments visuels, formules ou mises en
page et la fidélité des résumés ne sont pas garanties.

Le manifeste `main` du dépôt `elise-hermes-haos` examiné ne monte que le volume
de données de l'application sur `/opt/data`. La candidate Memory ne monte pas `/share`. L'accès direct aux documents par
Hermès est à vérifier séparément sur la version réellement installée ; Bruno
pourra lui transmettre les documents ou leurs adresses. Le manifeste examiné
indique 0.1.0 alors que la version 0.1.2 est rapportée en service ; il serait
incorrect d'en déduire la configuration réelle de celle-ci.

La voie cible reste : Hermès lit le document accessible, repère ses limites
d'extraction, prépare des faits sourcés, puis utilise Memory pour les gérer.
Avant d'enregistrer, il convient de signaler toute partie non lue, incertaine
ou interprétée. Ne pas inventer un fait ; en cas de conflit, conserver les
sources et les dates. Assist reste également capable d'alimenter Memory.

Sources exactes : [extraction Hermès v0.23.0](https://github.com/NousResearch/hermes-agent/blob/v0.23.0/tools/read_extract.py),
[skill PDF v0.23.0](https://github.com/NousResearch/hermes-agent/blob/v0.23.0/skills/productivity/pdf/SKILL.md),
[manifest Hermès du dépôt](https://github.com/brunofoxmulder/elise-hermes-haos/blob/main/elise_hermes_haos/config.yaml).
