# CH-REVIEWQ-20261118 — Diagnostic exploratoire correctif B

**Statut : analyse uniquement, aucune correction B implémentée.**

## Sources examinées
Dépôt amont `ipiton/agent-memory-mcp` figé sur `dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b` :
- `internal/sessionclose/plan.go`
- `internal/sessionclose/apply.go`
- `internal/server/session_tracker.go`
- `internal/sessionclose/sessionclose.go`

## Faits
1. `sessionTracker.flushSession` appelle `closeService.Analyze`, puis `persistReviewQueue`.
2. `persistReviewQueue` parcourt les actions à l'état `review_required` et appelle `st.store.Store(ctx, mem)` pour chacune.
3. Aucun contrôle d'existence d'une fiche équivalente n'apparaît dans cette fonction.
4. `suppressReviewQueue` permet de désactiver cette persistance automatique ; le commentaire du code indique que les actions restent accessibles dans le résultat de clôture.
5. Le correctif A concerne exclusivement l'exclusion des fiches review queue des cibles de `planActions`.

## Hypothèse à tester
Une nouvelle clôture de session peut générer des fiches en attente équivalentes à des fiches non résolues. Ce mécanisme est compatible avec les doublons observés, sans prouver qu'il explique tous les cas de l'incident.

## Options à comparer avant développement
- **B1 :** garde d'idempotence dans `persistReviewQueue` pour une identité stable de proposition, limitée aux fiches encore en attente. Préserver les propositions réellement nouvelles et les changements substantiels.
- **B2 :** option existante de suppression de persistance automatique. Moins de bruit, mais change la disponibilité durable des propositions en attente : décision de gouvernance nécessaire.
- **B3 :** déduplication lors de la consultation ou de la résolution. Préserve les écritures mais laisse croître le stock et ne prévient pas les doublons en base.

## Tests indispensables
- Deux clôtures identiques : une seule fiche en attente.
- Propositions distinctes, même contexte : deux fiches conservées.
- Proposition modifiée substantiellement : ne pas supprimer silencieusement.
- Fiche résolue puis nouvelle proposition : comportement défini et vérifié.
- Sessions simultanées : vérifier l'atomicité ; éviter le doublon entre recherche et écriture.
- Aucune suppression ou fusion automatique des fiches existantes.

## Risques et limites
L'absence de garde dans une fonction n'établit pas l'absence d'une déduplication plus bas dans `Store`. Vérifier les mécanismes du stockage, la sémantique de la review queue et les vrais cas d'incident avant de coder. Ne pas modifier la configuration de production sans autorisation explicite.

**Décision :** B reste ouvert, sans patch ni déploiement. Correctif A et PR #19 inchangés dans leur périmètre fonctionnel.

## Vérification complémentaire du stockage (18/11/2026)
Source : `internal/memory/write.go` au commit amont figé.

- `Store` valide le souvenir, calcule éventuellement son embedding (sauf pour les fiches review queue), prend `writeMu`, attribue un UUID si nécessaire, puis appelle `insertMemoryRow`.
- La fonction ne vérifie pas l'existence d'un contenu ou d'une proposition équivalente. `writeMu` sérialise les écritures, mais ne constitue pas une règle d'unicité sémantique.
- Les fiches review queue sont explicitement exclues de la génération d'embeddings, ce qui rend une déduplication par recherche vectorielle inadaptée à ce chemin.
- **Conséquence :** une prévention fiable doit utiliser une identité métier stable et/ou une contrainte transactionnelle appropriée ; une simple recherche suivie d'un `Store` laisse un risque de concurrence.

**Niveau de certitude :** élevé pour l'absence de déduplication dans `Store` ; moyen pour l'attribution de tous les doublons observés au `sessionTracker`, faute de reconstitution de chaque événement.

## Identité des propositions : vérification du rendu
Source supplémentaire : `internal/server/session_review_queue.go` (commit amont figé).

- `reviewQueueTitle` assemble le titre de l'action et, le cas échéant, le service : **ce n'est pas une clé d'unicité**.
- `reviewQueueContent` inclut action, handling, cible affichée ou identifiant, raison, trace et seulement les **220 premiers caractères** du contenu candidat.
- Une comparaison sur le titre peut fusionner deux propositions différentes ; une comparaison sur le contenu affiché peut manquer des changements au-delà des 220 caractères.
- Les champs `TargetMemoryID`, `Candidate.Content`, `Kind`, `Context`, `Service` et l'état de validation doivent être considérés séparément pour définir l'identité métier.

### Critères de conception proposés (non validés)
1. Définir une empreinte stable à partir de champs structurés normalisés : contexte, service, type d'action, identifiant cible (si présent), contenu **complet** du candidat, et éléments métier discriminants.
2. Limiter la recherche d'équivalence aux fiches encore **en attente** ; une proposition résolue ne doit pas bloquer silencieusement une nouvelle demande.
3. Préserver une nouvelle fiche lorsque la cible, le sens de l'action ou le contenu substantiel change.
4. Traiter les créations simultanées par un mécanisme transactionnel ou une contrainte d'unicité explicite, pas par un simple `List` suivi de `Store`.
5. Ne pas réutiliser `reviewQueueContent` comme empreinte : son contenu est une présentation tronquée.
6. Avant tout patch, vérifier la représentation réelle des états de résolution et la compatibilité des anciens enregistrements.

**Point non tranché :** une proposition répétée après résolution doit-elle être recréée systématiquement ou soumise à une règle de délai ? À arbitrer avec Bruno ; ne pas inventer cette politique.
