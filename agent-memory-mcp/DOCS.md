# Agent Memory MCP

Memory conserve les souvenirs et les rend accessibles aux assistants autorisés,
y compris Assist et Hermès. La présente version est une candidate : sa mise en
service sur Home Assistant doit être validée séparément.

## Avant toute mise à jour

Vérifier une sauvegarde cohérente et restaurable et conserver la version
précédente. L'arrêt peut provoquer une consolidation de session. Le code garde
l'identifiant d'application et le chemin de données de la version 0.1.1.
Une mise à jour avec un souvenir fictif a été testée ; ce n'est pas une
restauration Home Assistant réelle.

La candidate déclare une mise à jour nécessitant l'attention de l'utilisateur
pour éviter une installation automatique. Selon la documentation Home Assistant,
une sauvegarde de l'application inclut son dossier de configuration public ;
il faut néanmoins vérifier la sauvegarde et sa restauration sur l'installation
réelle. La sauvegarde à froid arrête l'application pendant sa création.

## Vectorisation

Les vecteurs permettent de rechercher les souvenirs par le sens. Cette fonction
est désactivée par défaut. Son fournisseur est indépendant du LLM conversationnel.

- **API compatible OpenAI** : clé dans le champ masqué ; adresse et modèle
  configurables. Le modèle par défaut est `text-embedding-3-small`.
- **Ollama** : adresse et modèle configurables ; le modèle par défaut est
  `bge-m3:latest`. Il doit être installé sur le serveur Ollama.
- **Dimensions** : 1 024 par défaut, à adapter au modèle et à l'API choisis.

À l'activation, des souvenirs existants peuvent être automatiquement vectorisés
et leur contenu transmis au fournisseur choisi. Changer de fournisseur, modèle,
adresse ou dimensions peut déclencher une nouvelle vectorisation. Vérifier la
sauvegarde et le fournisseur avant activation.

Si la clé manque ou si le fournisseur est indisponible, la recherche par texte
peut prendre le relais, avec des résultats potentiellement moins complets.
L'état « configuré » dans le journal ne prouve pas que le fournisseur répond
ou que tous les souvenirs sont vectorisés.

## Accès MCP

Par défaut, Memory écoute sur le port 18080 sans authentification pour
préserver la compatibilité actuelle. Toute machine pouvant joindre ce port
peut potentiellement accéder aux outils, y compris la suppression.

Le jeton MCP facultatif protège les appels lorsqu'il est renseigné. Vérifier
que tous les clients, notamment Assist et Hermès, savent le transmettre avant
de l'activer : sinon ils peuvent perdre l'accès. HTTP ne chiffre pas le jeton
ni les données. Ne pas exposer le port sur Internet.

## Autres options

- **RAG documentaire** : désactivé par défaut. La surveillance nécessite
  l'indexation automatique. Un fournisseur distant peut recevoir le contenu
  des documents indexés.
- **Suivi de session** : activé par défaut ; la consolidation peut créer des
  éléments à revoir.
- **Classement par niveau** : désactivé par défaut ; il peut modifier l'ordre
  et exclure certains souvenirs hors de leur contexte.
- **Diagnostic strict** : désactivé par défaut ; il peut produire une erreur
  plutôt qu'une réponse de secours. À réserver au diagnostic.
- **Statistiques** : désactivées par défaut.

Hermès reste chargé de lire les documents ou adresses transmis par Bruno et
de préparer des souvenirs sourcés. Ses accès et formats réels restent à
vérifier. La candidate utilise SQLite ; PostgreSQL n'est pas implémenté.
