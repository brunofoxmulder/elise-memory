# CH-REVIEWQ-20261118 — audit de l'identité des événements source

Statut : audit statique du commit amont `dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b`, **aucune modification de production**.

## Faits lus dans le code

Dans `internal/server/session_tracker.go` :

- `flushSession(boundary, session)` construit `summary := session.summary(boundary)`, puis appelle `closeService.Analyze(... SaveRaw:true ...)`.
- `persistReviewQueue(ctx,boundary,result)` parcourt les actions et écrit chacune avec `st.store.Store(ctx,mem)`.
- `MetadataSessionBoundary` stocke `boundary`, qui désigne un mode de fermeture, pas un identifiant d'occurrence.
- Si `result.RawSummarySaved != ""`, `MetadataSourceSessionID` référence ce résumé sauvegardé.
- L'action expose `Kind`, `TargetMemoryID`, `Candidate` et `DecisionTrace` ; aucun identifiant d'action immuable n'a été établi dans les éléments inspectés.

## Risques

1. `boundary + action index` est insuffisant entre deux sessions différentes.
2. `RawSummarySaved + action index` peut identifier une action d'un résultat sauvegardé, mais **son invariance entre retries n'est pas démontrée**. Si un retry réexécute `Analyze` et sauvegarde un nouveau résumé, la clé change.
3. Une empreinte du contenu ne remplace pas un identifiant d'événement : deux événements distincts peuvent avoir le même contenu.
4. Une clé fabriquée à partir de l'heure de tentative casserait l'idempotence.

## Condition préalable à l'intégration

Vérifier le chemin de sauvegarde de `SaveRawSummaryWithOptions` et la sémantique de reprise de `Analyze`. Si le résumé source est recréé lors d'un retry, introduire une identité stable de clôture persistée **avant** l'analyse, puis une identité d'action stable dans cette clôture.

Sans cette garantie, `SaveEvent` doit rester expérimental ; ne pas l'appeler avec une clé synthétique prétendument stable.

## Tests à exiger

- Deux clôtures distinctes de même type avec une action identique : événements distincts.
- Retry d'une clôture interrompue avant la persistance : même événement.
- Retry après commit mais avant acquittement : aucune seconde occurrence.
- Plusieurs actions identiques dans la même clôture : identité d'action non ambiguë.
- Reprise après redémarrage et après convergence d'un second processus.

Décision : aucune écriture dans le magasin réel tant que ces garanties ne sont pas prouvées.
