# CH-REVIEWQ-20261118 — Correctif A : dossier de validation

Statut : **candidat validé en CI, non déployé**. PR #19 **draft**, non fusionnée.

## Anomalie ciblée
Lors de la planification des actions de clôture de session, les fiches de la *review queue* pouvaient être sélectionnées comme cibles de rapprochement. Une fiche en attente de validation n'est pas un souvenir validé.

## Correction
Dans `internal/sessionclose/plan.go`, exclusion de `memory.IsReviewQueueMemory(item)` en plus des résumés de session. Le dépôt amont est figé sur `dc404e4f3be140ea5c4e7a4fa282c02427e7cb9b` ; correctif appliqué via `review-queue-filter.patch`.

## Preuves automatisées
Commit testé : `1e1173f8936c5af4a1a497a9e0b67fe131f26e96`.

- GitHub Actions, `Agent Memory MCP — correctif A (isolated validation)`, exécution #13 : **success**.
- GitHub Actions, `Agent Memory candidate validation`, exécution #91 : **success**.
- GitHub Actions, `Élise Memory package validation`, exécution #258 : **success**.
- Le test Go `TestPlanActionsExcludesPendingReviewQueue` utilise une base SQLite jetable et appelle la vraie méthode `planActions` : fiche en attente exclue, mémoire ordinaire éligible.
- Construction de l'image et vérifications génériques réalisées sur données fictives.

## Limites / risques résiduels
- Pas de preuve que le correctif élimine les doublons de la review queue (correctif B distinct).
- Pas de preuve qu'il résout les références à des identifiants inexistants.
- Pas de migration ni de réparation rétroactive des fiches déjà produites.
- Le test cible `planActions`, pas l'ensemble du flux `Analyze` jusqu'à la création de la fiche en attente.
- Pas d'essai sur l'instance Home Assistant de production.

## Décision et déploiement
**Aucune autorisation de déploiement accordée.** Ne pas fusionner la PR, mettre à jour l'add-on ou modifier la base mémoire sans validation explicite de Bruno dans une séance Maison Cognitive.

Avant un déploiement éventuel : confirmer une sauvegarde restaurable, inventorier la version installée et les dépendances, prévoir un retour arrière, puis demander l'autorisation explicite.
