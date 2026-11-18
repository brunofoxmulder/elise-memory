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
