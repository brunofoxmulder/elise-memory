# CH-REVIEWQ-20261118 — Correctif B : contrat de conception et tests

Statut : **conception en branche isolée, aucun déploiement, aucun correctif fonctionnel appliqué**.
Décision fonctionnelle approuvée par Bruno : une fiche en attente par proposition unique ; conserver les récurrences ; ne rouvrir une fiche résolue que sur fait nouveau vérifiable ; ne jamais effacer une décision validée automatiquement.

## Sources et portée
- Amont figé : `ipiton/agent-memory-mcp@dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b`.
- `internal/server/session_tracker.go::persistReviewQueue` écrit chaque action en attente via `st.store.Store`, sans déduplication.
- `internal/server/session_review_queue.go` produit une présentation dont `Candidate.Content` est tronqué à 220 caractères ; ne jamais utiliser cette présentation comme identité.
- `internal/sessionclose/plan_fingerprint.go` apparaît dans une version amont plus récente, **absente du commit figé**. Son usage n'est ni une dépendance ni une solution acquise.
- Correctif A testé séparément dans PR #19 : exclusion des fiches de review queue comme cibles. B ne doit pas masquer les défauts de ciblage.

## Contrat métier à implémenter après vérification du stockage
1. **Identité** : version de schéma + projet/contexte + service + type d'ingénierie + type d'action + identifiant stable de la cible + périmètre/entité + empreinte du contenu complet du candidat. Ne pas dédupliquer seulement par titre, texte tronqué, ou nom d'action.
2. **En attente** : une proposition équivalente accroît `seen_count` et actualise `last_seen_at` de manière atomique ; conserver date de première observation et références de provenance sans effacer les précédentes.
3. **Résolue** : conserver l'historique et la décision. Une nouvelle fiche n'est admissible qu'avec preuve datée d'une information nouvelle pertinente ou changement substantiel de version/contenu de la cible. Une simple actualisation de `last_verified_at` n'est pas une preuve suffisante.
4. **Concurrence** : la vérification d'existence et l'insertion/incrément doivent être transactionnelles. Un `List` suivi d'un `Store` sans garantie ne suffit pas.
5. **Traçabilité** : les compteurs « traité / restant » portent sur les fiches, tandis que les récurrences sont une métrique distincte. Ne jamais modifier automatiquement les fiches historiques déjà résolues.
6. **Compatibilité** : prévoir une stratégie explicite pour les fiches anciennes dépourvues d'empreinte, sans migration destructrice.

## Tests d'acceptation requis
- Deux clôtures identiques : une fiche en attente, `seen_count=2`, dates cohérentes.
- Deux actions de même titre mais cibles distinctes (porte / réfrigérateur / congélateur) : trois fiches.
- Sauvegardes 14/11 vs 15/11 : contenu/version modifié, aucune fusion abusive.
- Little Monkey : dégradation vs retour à la normale, deux faits distincts.
- Texte candidat différent après le caractère 220 : propositions distinctes.
- Deux créations concurrentes : une fiche, compteur exact.
- Fiche résolue + simple relecture sans fait nouveau : aucune réouverture.
- Fiche résolue + nouvelle preuve pertinente : nouvelle fiche liée à l'ancienne, sans mutation de la décision.
- Aucune cible de type review queue après correctif A.
- Aucun changement de production, aucun déploiement, aucune suppression/fusion automatique.

## Vérifications techniques encore nécessaires
- Représentation des statuts de résolution et provenance des preuves.
- Schéma SQLite, transactions, contraintes uniques et chemin d'écriture des métadonnées.
- Définition canonique de la cible et de l'entité quand l'action ne possède pas d'identifiant.
- Compatibilité avec la version du patch A et stratégie d'intégration ultérieure.

## Porte de validation
Implémenter et exécuter les tests sur cette branche isolée ; demander ensuite à Bruno une validation explicite avant fusion ou déploiement. Une branche GitHub n'autorise aucune intervention dans Home Assistant.

## Vérifications du code figé — persistance et résolution (18/11/2026)
Sources lues au commit amont épinglé :
- `internal/memory/write.go::Store` : `ms.writeMu` protège l'insertion individuelle et `insertMemoryRow` est appelé sous ce verrou ; **aucune recherche d'équivalence** dans ce chemin. L'absence d'embedding pour les fiches review queue est confirmée.
- `internal/memory/store_sql.go::insertMemoryRow` : `INSERT INTO memories (... metadata ...)` sans `ON CONFLICT` d'empreinte ; la vérification `RowsAffected()==1` protège contre une insertion silencieusement ignorée, pas contre les doublons sémantiques.
- `internal/review/resolve.go::ResolvedTags` : suppression des tags de review précédents puis ajout de `review:<resolution>` et `status:<resolution>`. Les résolutions admises incluent resolved, dismissed et deferred. Le simple changement de tags ne crée pas de verrou contre une re-proposition.

### Conséquences de conception
- Éviter un contrôle d'unicité uniquement dans `sessionTracker.persistReviewQueue` avec `List` puis `Store` : cette séquence n'est pas atomique et le verrou interne de `Store` ne couvre pas la lecture.
- Concevoir une primitive **au niveau Store**, assurant sous une même section critique/transaction : rechercher une fiche en attente avec empreinte identique, incrémenter son compteur ou insérer une nouvelle fiche. Examiner les transactions SQLite avant de choisir l'implémentation.
- Pour la réouverture après résolution, distinguer `resolved`, `dismissed`, `deferred` et préciser leur sens métier : `deferred` ne doit pas être interprété sans validation comme une décision définitive.
- Les fiches historiques sans empreinte nécessitent une politique de compatibilité explicite ; aucune modification automatique de l'historique n'est autorisée.

**Statut** : inspection statique et documentation seulement ; aucune preuve de test du correctif B à ce stade.

## Vérification du schéma SQLite au commit figé
Source : `internal/memory/memory.go`, fonction d'initialisation du magasin.

- La table `memories` possède `id TEXT PRIMARY KEY`, `metadata TEXT`, `tags TEXT`, `context TEXT` et des dates ; aucun index d'unicité métier de proposition n'est déclaré dans ce schéma initial.
- Index observés : type, contexte, importance et date de création. Ils ne garantissent pas l'unicité des fiches de review queue.
- Le magasin charge les souvenirs dans un cache (`memories`, `contextIndex`) au démarrage. Une écriture directe en SQL doit préserver la cohérence du cache ; ne pas contourner les invariants de `Store`.

### Choix technique provisoire
Étudier une primitive dédiée au magasin qui coordonne transaction SQLite, verrou d'écriture et mise à jour du cache. Le design exact de l'index d'unicité, de la migration des données existantes et de la représentation du statut reste à tester. **Ne pas introduire une contrainte unique générale sur les souvenirs** : elle pourrait affecter des données hors review queue.

### Test de panne indispensable
Simuler une erreur entre incrément SQL et synchronisation du cache, puis vérifier qu'un redémarrage restitue un compteur exact et qu'aucun succès trompeur n'est retourné.

**État :** analyse du schéma confirmée ; pas encore de code B ni de tests exécutés.
