# Élise Memory — architecture de connaissance

## But
La base SQLite locale est une mémoire opérationnelle compilée, pas une copie de Google Drive.

## Couches
- **canonique** : connaissances structurelles actuelles issues des sources vivantes officielles Maison Cognitive ;
- **REX** : observations apprises, candidates puis validées/rejetées, toujours traçables ;
- **temporal** : contexte de cycle et de conversation, conservé par le moteur existant.

Un REX ne modifie jamais silencieusement une connaissance canonique. Une contradiction doit rester visible. Un REX validé pourra être promu vers le jumeau numérique après validation explicite.

## Sources retenues pour house
1. `Home Assistant / Référentiel métier` : presque intégral, cœur sémantique.
2. `00_Index / 09_Relations fonctionnelles` : uniquement relations validées/actives.
3. `Automatisations / Automatisations` : sémantique de la production active (nom, domaine, descriptif, relations, inventaire utile), sans YAML, Test ni Production -1.
4. `Automatisations / Référentiel HA` : enrichissement seulement des entités effectivement référencées par une connaissance.
5. `Scripts - Maison Cognitive / Scripts Pyscript` : scripts actifs/production utiles, rôle, service, entrées/sorties essentielles ; pas le code.
6. `Home Assistant / Mémoire IA` : connaissances explicitement validées (statut validé/validée, y compris libellé qualifié).
7. Décisions : uniquement celles encore valides qui modifient le sens actuel de la maison.

## Exclus par défaut
Données brutes, historiques thermiques, Journal projet en masse, incidents clos, hypothèses, tests, archives, Production -1, code/Pyscript brut, prompts et YAML brut. Ils restent des preuves ou sources de reprise.

## Synchronisation nocturne
Pipeline prévu : Index des sources officielles -> lecture -> validation des schémas -> normalisation -> contrôle de cohérence -> transaction SQLite -> publication de la nouvelle vue.

Garanties :
- aucune écriture Google Drive ou Home Assistant ;
- ligne vide ignorée ;
- contenu inchangé = aucun doublon ;
- contenu changé = ancienne version supersédée ;
- source indisponible ou schéma invalide = dernière vue valide conservée ;
- aucune demi-synchronisation ;
- provenance exacte conservée ;
- dérive anormale de volume rejetée et signalée.

La cadence nocturne sera configurable ; aucune heure précise n'est imposée tant qu'elle n'a pas été validée.


## Publication transactionnelle

Une compilation canonique complète est publiée en une transaction SQLite. Avant bascule :
- snapshot vide interdit ;
- identité canonique dupliquée interdite ;
- chute de volume supérieure au seuil de sécurité interdite ;
- une erreur laisse intégralement en place la dernière vue valide.

Lors d'une publication valide, les contenus inchangés ne sont pas dupliqués, les contenus modifiés supersèdent leur version précédente et les connaissances disparues de la source deviennent inactives sans effacement historique. La couche REX n'est jamais modifiée par une synchronisation canonique.


## Accès Google Sheets

Le lecteur nocturne utilise l'API Google Sheets v4 avec le scope strict `spreadsheets.readonly`. Il n'expose aucune méthode d'écriture et n'effectue aucune découverte générale de Google Drive : les identifiants de classeurs, noms d'onglets et plages autorisées sont explicitement enregistrés dans le code.

Pour une exécution autonome sur HAOS, l'option préparée est un compte de service dédié dont le fichier d'identifiants est fourni au conteneur de manière sécurisée. Les seuls classeurs nécessaires devront être partagés avec ce compte. La clé privée ne doit jamais être placée dans GitHub, dans SQLite, dans les logs ou dans le jumeau numérique.

Google recommande les identifiants éphémères lorsqu'ils sont disponibles et avertit du risque des clés de compte de service. HAOS n'étant pas une ressource Google Cloud à laquelle on peut simplement attacher un compte de service, le choix opérationnel final des identifiants reste à valider avant déploiement. Le code actuel prépare le lecteur mais ne configure ni ne déploie aucun secret.
