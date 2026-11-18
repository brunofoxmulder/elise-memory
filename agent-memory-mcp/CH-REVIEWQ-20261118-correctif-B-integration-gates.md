# Correctif B — conditions d'intégration au magasin réel

Statut : conception / lecture seule, **non intégré**, non déployé. Branche de test uniquement.

## Source amont inspectée
Dépôt `ipiton/agent-memory-mcp`, commit épinglé `dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b`.

- `internal/server/session_tracker.go::persistReviewQueue` appelle actuellement `st.store.Store(ctx, mem)` pour chaque action à revoir, sans clé d'unicité.
- `internal/memory/write.go::Store` valide, prend `writeMu`, insère `memories`, vérifie la persistance, puis met à jour le cache sous `mu`.
- `internal/memory/store_sql.go::insertMemoryRow` accepte un exécuteur SQL, y compris une transaction `*sql.Tx`.
- `internal/memory/memory.go::Store` maintient un cache et un mécanisme de convergence des écritures externes.

## Contrat requis avant activation

1. Une **seule** primitive publique `StoreReviewOccurrence` doit remplacer l'appel direct à `Store` uniquement dans `persistReviewQueue`; les autres écritures de mémoire conservent leur comportement.
2. Sous `writeMu`, transaction SQL unique : vérifier la clé, insérer la fiche `memories` et son lien d'identité, ou incrémenter une occurrence en attente. La contrainte UNIQUE en base reste l'arbitre entre processus.
3. Une collision de clé retourne l'ID historique et n'écrase jamais titre, contenu, tags, décision ni provenance initiale.
4. Ne publier la nouvelle fiche dans le cache **qu'après** commit. Les occurrences déjà présentes ne doivent pas produire une entrée cache supplémentaire.
5. Les fiches `resolved`, `dismissed` et `deferred` restent immuables. La création d'une nouvelle révision nécessite une preuve vérifiée, reliée à la décision antérieure ; aucune simple modification textuelle ne vaut preuve.
6. Les horodatages d'occurrence ne régressent pas. Une répétition d'appel après timeout doit être idempotente sur une clé d'événement persistée, et non simplement incrémenter une seconde fois.
7. Ne pas activer automatiquement la migration des fiches historiques. Faire un inventaire en lecture seule des identités absentes, collisions et références orphelines ; exiger une décision explicite pour toute reprise.
8. L'absence de lien valide ou une incohérence entre cache et SQL doit faire échouer l'opération de manière observable, sans suppression automatique.

## Tests bloquants

- Écriture nouvelle / répétition / concurrence entre processus / rollback et erreur SQLite.
- Cache cohérent après commit, après rollback et après redémarrage ; convergence via watcher.
- Même titre avec faits distincts, titre reformulé pour même sujet, contenu intégral >220 caractères.
- Décision conservée et nouvelle révision explicitement liée, sans réouverture automatique.
- Idempotence de replay après interruption et absence de double comptage.
- Données historiques réelles anonymisées : doublons, fiches résolues, références orphelines.
- Tests combinés des correctifs A et B sur le commit amont épinglé.

## Décision

Aucune modification du Dockerfile, de l'add-on HAOS, de Home Assistant ou des mémoires de production. Ce document n'autorise ni fusion ni déploiement.

## Audit de la branche de test — anomalie corrigée

Le prototype `atomic.go` contenait des séquences littérales `\\n` dans une instruction SQL entre backticks pour `prototype_review_events`. SQLite aurait refusé la création de la table : les tests ajoutés n'étaient donc pas probants tant qu'ils n'étaient pas exécutés. La chaîne SQL a été corrigée au commit `98f5b81ebbb05feba5769934aeae3b25a00cf272`. Attendre une exécution CI réussie avant d'affirmer que `SaveEvent` fonctionne.

**Priorité désormais** : ne plus ajouter de nouveaux prototypes. Implémenter le chemin de production `persistReviewQueue -> StoreReviewOccurrence` dans un patch appliqué au code amont épinglé, puis exécuter les tests combinés A+B. La preuve d'identité stable entre retries reste un prérequis pour activer le comptage exactement une fois.
