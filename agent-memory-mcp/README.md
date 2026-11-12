# Agent Memory MCP — mémoire partagée

Cette application Home Assistant fournit une mémoire accessible par MCP aux
assistants autorisés à l'utiliser, notamment Assist et Hermès. Le fournisseur
d'embeddings est choisi séparément du modèle conversationnel : changer de LLM
dans Assist ne doit pas imposer de changer la mémoire.

## État de cette branche

La version 0.1.2-dev.1 est une **candidate en préparation**, non validée sur
l'installation Home Assistant de Bruno. La version 0.1.1 constitue la référence
documentée en service ; elle a validé la mémorisation et le rappel explicites.
Les options décrites ci-dessous concernent la candidate, pas nécessairement la
version déjà installée.

Le service utilise actuellement une base SQLite persistante sous
`/config/memory-data`. PostgreSQL n'est pas pris en charge par cette candidate.
La recherche documentaire peut utiliser le dossier `/config/memory-documents` ou, au choix, `/share/memory-documents`.

## Choix de vectorisation

Les embeddings sont désactivés par défaut. Lorsqu'ils sont activés, l'application
utilise le fournisseur sélectionné :

| Réglage | API compatible OpenAI | Ollama |
| --- | --- | --- |
| Adresse | Configurable ; API OpenAI par défaut | Configurable ; `http://127.0.0.1:11434` par défaut |
| Modèle | Configurable ; `text-embedding-3-small` par défaut | Configurable ; `bge-m3:latest` par défaut |
| Dimensions | Configurables ; 1024 par défaut | Configurables ; 1024 par défaut |
| Clé API | Champ masqué, requis par la candidate | Non requise par la candidate |

Le fournisseur API doit accepter le format attendu par le client OpenAI,
y compris le paramètre de dimension. Pour Ollama, le modèle doit être installé
sur le serveur choisi et produire le nombre de dimensions configuré.
La compatibilité de chaque fournisseur ou modèle reste à vérifier.

Le serveur Ollama doit être joignable depuis l'application ; l'adresse par
défaut ne désigne pas automatiquement une autre machine du réseau. L'adresse
configurée détermine où les textes sont envoyés.

Le fournisseur et le modèle Ollama sélectionnés sont verrouillés : la candidate
ne doit pas basculer automatiquement vers un autre fournisseur ou modèle en
cas d'échec. Une indisponibilité peut donc empêcher la vectorisation ou le
rappel sémantique ; elle ne constitue pas une raison d'inventer une réponse.

## Attention aux souvenirs existants

À l'activation des embeddings, le moteur amont peut **vectoriser
automatiquement les souvenirs existants**. Leur contenu peut alors être envoyé
à l'adresse du fournisseur configuré. Un changement de fournisseur, de modèle
ou de dimension peut entraîner une nouvelle vectorisation ; la compatibilité
et la reconstruction éventuelle de l'index documentaire sont à examiner.

Avant toute activation réelle : sauvegarde contrôlée et restaurable, choix du
fournisseur et validation explicite de Bruno. La sauvegarde de la candidate est
configurée à froid ; son fonctionnement réel et sa restauration restent à
vérifier. À l'arrêt, le moteur peut écrire des éléments de consolidation de
session ; il faut en tenir compte lors de la préparation de la sauvegarde.

## Recherche documentaire

Le RAG, l'indexation automatique et la surveillance sont désactivés par défaut.
L'option de source choisit le dossier de l'application ou `/share/memory-documents` ; ce dernier doit être créé avant le démarrage s'il est sélectionné. Le dossier `/share` entier est monté dans le conteneur en lecture seule, même si le dossier de l'application est choisi : cela limite les écritures, mais ne rend pas les autres fichiers du partage inaccessibles au processus. L'exposition des outils et l'accès aux documents restent à sécuriser avant mise en service.
La surveillance nécessite le RAG et l'indexation automatique. L'index contient
des données dérivées des documents ; avec un fournisseur distant, leur contenu
peut être transmis pour vectorisation. Le dossier de documents et les droits
d'accès sont à définir avant toute utilisation avec des fichiers réels.

Les documents indexés et les souvenirs sont deux usages distincts : indexer un
fichier ne garantit pas que ses informations deviennent des souvenirs
structurés. La production et la vérification de souvenirs issus de documents
restent à organiser avec Hermès et Assist. L'examen du moteur épinglé montre qu'il accepte les fichiers Markdown et
certains fichiers reconnus par des conventions de nom ou de chemin. Il ne
contient pas d'extracteur de texte PDF, Word ou tableur dans ce parcours.
Certains noms particuliers peuvent même être classés sans vérifier le format :
ne pas déposer de fichier binaire dans le dossier indexé avant d'avoir prévu
une conversion contrôlée.

Le moteur lit le fichier retenu, retire notamment l'en-tête YAML Markdown s'il
existe, puis découpe son texte en fragments. Le filtrage peut écarter des
sections jugées peu utiles. Une recherche ne renvoie que des fragments
sélectionnés : elle ne garantit donc pas l'interprétation complète du document.
Hermès est chargé de lire et digérer les documents, puis de préparer les
souvenirs structurés avec leur source. Ses capacités effectives selon les
formats et le contrôle de fidélité restent à vérifier. La conversion n'est
pas une fonction à ajouter à Memory par défaut. Aucun fichier réel n'a été lu
pour cette vérification.

## Connexion et sécurité

L'endpoint de la candidate est `http://homeassistant.local:18080/mcp`.
**L'accès MCP reste actuellement sans authentification**, pour préserver la
compatibilité avec le client existant. Toute personne ou machine pouvant
joindre ce port peut potentiellement lire ou modifier la mémoire et accéder
aux autres outils exposés. La protection réseau et l'authentification restent
à résoudre avant déploiement ; ne pas exposer ce port sur Internet.

Les outils visibles par le serveur ne garantissent pas que chaque assistant
les appelle spontanément : le raccordement et les instructions de chaque
client doivent être vérifiés. Le partage Assist / Hermès et les permissions
précises de chaque client restent à valider sur l'installation réelle.

## Vérifications et limites

Les essais automatisés de la candidate construisent l'image et utilisent des
services simulés et des données fictives ; ils couvrent notamment les choix
de fournisseur, le verrouillage, les dimensions, l'indexation et un scénario
de sauvegarde/restauration de copie arrêtée. Ils ne remplacent ni une recette
HAOS, ni une restauration Supervisor réelle, ni une validation avec tous les
modèles ou fournisseurs.

Aucun déploiement ni changement de la mémoire de production n'est autorisé
par ce document. Les évolutions, les réglages et la mise en service doivent
être examinés et validés dans le cadre du projet Maison Cognitive.
