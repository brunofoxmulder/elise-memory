# Raccordement préparatoire d'Hermès à Agent Memory MCP

Statut : proposition de configuration, non appliquée et non testée sur
l'installation HAOS réelle. Branche candidate Memory 0.1.2-dev.1.

## But

Hermès et les agents Assist peuvent utiliser le même serveur et la même base
de souvenirs, indépendamment de leurs modèles conversationnels. Hermès peut
préparer et alimenter les souvenirs ; Assist peut les consulter et également
les alimenter selon les instructions retenues par Bruno. L'accès d'Hermès à
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
Hermès. La liste permet de présenter la mémoire et la recherche documentaire ;
elle ne règle pas les autorisations des actions.

**Attention : `memory` regroupe notamment lecture, écriture, modification et
suppression.** Autoriser cet outil ne limite donc pas Hermès à la lecture et
l'écriture. Une règle dans le prompt est une consigne, pas une protection
technique. La séparation des droits exige un contrôle serveur par action ou
un intermédiaire adapté ; ne pas présenter ce filtrage comme une sécurité.

## Conditions préalables à la mise en service

1. Reconstituer la configuration et les accès réellement en place, sans
   afficher les secrets ; vérifier les sauvegardes et la possibilité de retour
   arrière.
2. Résoudre l'accès réseau non authentifié et choisir les permissions effectives
   de chaque client. Maintenir l'accès HA d'Hermès en lecture seule.
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

La suppression des données de test doit être décidée et exécutée séparément.
La disponibilité du RAG et des embeddings dépend de leur configuration propre ;
un échec réseau ou de modèle ne doit pas être interprété comme un souvenir
absent. Les appels de rappel peuvent modifier des statistiques d'accès.

## Ce qui reste à construire ou vérifier

Contrôle d'accès par action, authentification et confidentialité réseau,
raccordement effectif d'Hermès et d'Assist, règles de qualité des souvenirs,
indexation documentaire réelle, sauvegarde et restauration HAOS. PostgreSQL
n'est pas implémenté dans la candidate actuelle.
