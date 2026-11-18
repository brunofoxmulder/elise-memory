package memory

import (
 "context"
 "errors"
 "fmt"
 "strings"

 "github.com/google/uuid"
)

// StoreReviewOccurrence stages the actual memories-table transaction.
// This file is not part of the add-on build until an upstream patch is wired.
func (ms *Store) StoreReviewOccurrence(ctx context.Context, fingerprint string, m *Memory) (string, int, error) {
 if ms == nil || m == nil || strings.TrimSpace(fingerprint) == "" {
  return "", 0, errors.New("review fingerprint and memory required")
 }
 if !IsReviewQueueMemory(m) { return "", 0, errors.New("review-queue memory required") }
 if err := m.Validate(); err != nil { return "", 0, err }

 ms.writeMu.Lock()
 defer ms.writeMu.Unlock()

 // DDL is additive; existing memories are not modified or backfilled.
 if _, err := ms.db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS review_occurrence_links (
  fingerprint TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL UNIQUE,
  seen_count INTEGER NOT NULL CHECK(seen_count >= 1),
  last_seen_unix_ns INTEGER NOT NULL
 )`); err != nil { return "", 0, fmt.Errorf("create review link schema: %w", err) }

 tx, err := ms.db.BeginTx(ctx, nil)
 if err != nil { return "", 0, err }
 defer tx.Rollback()

 if m.ID == "" { m.ID = uuid.NewString() }
 now := ms.now()
 // Claim the unique fingerprint FIRST, so competing SQLite writers serialize
 // before any memory row is inserted. Never insert a throwaway duplicate row.
 claim, err := tx.ExecContext(ctx, `INSERT INTO review_occurrence_links
 (fingerprint,memory_id,seen_count,last_seen_unix_ns)
 VALUES(?,?,1,?) ON CONFLICT(fingerprint) DO NOTHING`,
 fingerprint,m.ID,now.UTC().UnixNano())
 if err != nil { return "", 0, fmt.Errorf("claim review fingerprint: %w", err) }
 claimed, err := claim.RowsAffected()
 if err != nil { return "", 0, err }

 if claimed == 1 {
  m.CreatedAt, m.UpdatedAt, m.AccessedAt = now, now, now
  if err := insertMemoryRow(tx,m); err != nil { return "", 0, err }
  if err := tx.Commit(); err != nil { return "", 0, err }
  ms.mu.Lock()
  ms.cacheSetLocked(toCachedMemory(m))
  ms.mu.Unlock()
  return m.ID, 1, nil
 }
 if claimed != 0 { return "", 0, fmt.Errorf("unexpected fingerprint claim count %d", claimed) }

 // Exact JSON tag membership, not substring matching. The existence check
 // rejects orphaned links; resolved/dismissed/deferred decisions are immutable.
 var existingID string
 var count int
 err = tx.QueryRowContext(ctx, `UPDATE review_occurrence_links
 SET seen_count=seen_count+1,
 last_seen_unix_ns=MAX(last_seen_unix_ns,?)
 WHERE fingerprint=?
 AND EXISTS (
   SELECT 1 FROM memories m
   WHERE m.id=review_occurrence_links.memory_id
   AND EXISTS (SELECT 1 FROM json_each(m.tags) WHERE value='review:required')
   AND NOT EXISTS (
     SELECT 1 FROM json_each(m.tags)
     WHERE value IN ('review:resolved','review:dismissed','review:deferred')
   )
 )
 RETURNING memory_id,seen_count`,now.UTC().UnixNano(),fingerprint).Scan(&existingID,&count)
 if err != nil {
  return "", 0, fmt.Errorf("review occurrence rejected or unavailable: %w", err)
 }
 if err := tx.Commit(); err != nil { return "", 0, err }
 return existingID, count, nil
}
