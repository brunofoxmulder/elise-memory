# Correctif B — contrat d'intégration au Store (inspection du commit figé)

Statut : spécification technique, **pas de patch runtime**. Source : `ipiton/agent-memory-mcp@dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b`.

## Faits vérifiés
- `internal/server/session_tracker.go::persistReviewQueue` appelle `st.store.Store(ctx, mem)` une fois par action review-required ; il construit des métadonnées de session (`session_boundary`, `source_session_id`) qui **changent entre clôtures**. Elles ne doivent pas entrer dans l'identité stable.
- `internal/memory/write.go::Store` protège l'insertion par `writeMu`, vérifie la lecture après écriture, puis alimente `cacheSetLocked`.
- `internal/memory/write.go::Update` protège par `writeMu` et délègue à `updateLocked`. Ce dernier effectue `Get`, fusion des métadonnées, `updateMemoryRow`, puis `cacheSetLocked` sous le même verrou externe.
- `Update.Metadata` fusionne les champs fournis avec ceux existants ; une valeur vide **supprime** la clé. Pour le compteur, ne jamais remplacer toutes les métadonnées de provenance.
- `updateLocked` ne réalise pas de `verifyMemoryPersisted` explicite après mise à jour, contrairement à `Store`. Ce comportement existant ne suffit pas à prouver une récupération atomique de la file en cas d'échec.
- Le prototype B validé en CI utilise une table séparée et `INSERT ... ON CONFLICT ... RETURNING`. Il ne met pas à jour le cache des souvenirs de l'application.

## Contrat proposé pour une primitive Store intégrée
1. Entrée : fiche de proposition complète, empreinte versionnée et preuve structurée du changement ; exclure les champs de session éphémères de l'empreinte.
2. En une transaction et avec `writeMu`, rechercher l'identité dans l'ensemble des fiches review queue ; distinguer pending, deferred, resolved et dismissed.
3. Si pending : augmenter `seen_count` et `last_seen_at`, conserver `created_at`, les décisions et la provenance initiale ; éventuellement journaliser la nouvelle session dans une collection bornée.
4. Si deferred : **ne pas** ouvrir une nouvelle fiche par défaut ; préciser le mode de rappel à valider.
5. Si resolved/dismissed : ne pas rouvrir sans preuve nouvelle vérifiable ; conserver la fiche et la décision précédentes.
6. Si nouvelle identité : créer une fiche. Aucun nettoyage automatique des historiques.
7. À la validation de transaction : mettre le cache en cohérence sous les verrous existants ; une erreur de synchronisation doit être détectable et récupérable par rechargement.
8. Plusieurs processus partageant SQLite : `writeMu` est local au processus ; ajouter une contrainte SQL/transaction qui interdit les doublons entre processus. Les tests avec `SetMaxOpenConns(1)` ne démontrent **pas** cette propriété.
9. Éviter toute migration qui créerait un index unique sur tous les souvenirs. Examiner une table d'identités dédiée, ou un index partiel dont la compatibilité avec les données historiques est prouvée.

## Tests bloquants avant raccordement
- Concurrence sur connexions SQLite distinctes et deux processus ; aucune double fiche.
- Échec au milieu de la transaction : aucune moitié de compteur/fiche validée.
- Mise à jour du cache puis redémarrage ; état identique à la base.
- Même texte, cibles ou équipements différents ; jamais fusionnés.
- Clôtures répétées avec `boundary` et `source_session_id` différents ; même identité.
- Historique sans empreinte : conservation et politique de migration explicite.
- Résolution concurrente avec nouvelle occurrence : pas de réouverture accidentelle.
- Validation conjointe avec correctif A avant tout déploiement.

**Décision non prise** : choix de la structure SQLite finale, migration et stratégie multi-processus. Aucun changement HA ou add-on autorisé par cette note.
