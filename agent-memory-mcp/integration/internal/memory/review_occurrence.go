package memory

import (
 "context"
 "database/sql"
 "errors"
 "fmt"
 "strings"
 "time"

 "github.com/google/uuid"
)

// StoreReviewOccurrence is the intended real-store write boundary for review
// queue items. Unlike the isolated prototype it writes to the actual memories
// table, and publishes cache entries only after a successful SQL commit.
// Integration into upstream build and caller is a separate gated step.
func (ms *Store) StoreReviewOccurrence(ctx context.Context, fingerprint string, m *Memory) (string, int, error) {
 if ms == nil || m == nil || strings.TrimSpace(fingerprint) == "" {
  return "", 0, errors.New("review fingerprint and memory are required")
 }
 if !IsReviewQueueMemory(m) {
  return "", 0, errors.New("only review-queue memories are accepted")
 }
 if err := m.Validate(); err != nil { return "", 0, err }

 ms.writeMu.Lock()
 defer ms.writeMu.Unlock()

 // The unique index on fingerprint is authoritative across processes.
 // This schema is additive and does not alter existing review decisions.
 if _, err := ms.db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS review_occurrence_links (
  fingerprint TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL UNIQUE,
  seen_count INTEGER NOT NULL CHECK(seen_count >= 1),
  last_seen_unix_ns INTEGER NOT NULL
 )`); err != nil { return "", 0, fmt.Errorf("ensure review links: %w", err) }

 tx, err := ms.db.BeginTx(ctx, nil)
 if err != nil { return "", 0, err }
 defer tx.Rollback()

 var existingID string
 var existingCount int
 err = tx.QueryRowContext(ctx,
  `SELECT memory_id, seen_count FROM review_occurrence_links WHERE fingerprint=?`, fingerprint).
  Scan(&existingID, &existingCount)
 if err != nil && !errors.Is(err, sql.ErrNoRows) { return "", 0, err }
 if err == nil {
  // A previously resolved/dismissed/deferred review must not be modified.
  var tagsJSON string
  if err := tx.QueryRowContext(ctx,`SELECT tags FROM memories WHERE id=?`,existingID).Scan(&tagsJSON);err!=nil{return "",0,err}
  if strings.Contains(tagsJSON,"review:resolved") || strings.Contains(tagsJSON,"review:dismissed") || strings.Contains(tagsJSON,"review:deferred") {
   return "",0,errors.New("review decision is protected")
  }
  nowNS:=ms.now().UTC().UnixNano()
  if _,err:=tx.ExecContext(ctx,`UPDATE review_occurrence_links SET seen_count=seen_count+1,
   last_seen_unix_ns=MAX(last_seen_unix_ns,?) WHERE fingerprint=?`,nowNS,fingerprint);err!=nil{return "",0,err}
  if err:=tx.Commit();err!=nil{return "",0,err}
  return existingID,existingCount+1,nil
 }

 if m.ID=="" { m.ID=uuid.NewString() }
 now:=ms.now()
 m.CreatedAt=now
 m.UpdatedAt=now
 m.AccessedAt=now
 if err:=insertMemoryRow(tx,m);err!=nil{return "",0,err}
 if _,err:=tx.ExecContext(ctx,`INSERT INTO review_occurrence_links(fingerprint,memory_id,seen_count,last_seen_unix_ns)
 VALUES(?,?,1,?)`,fingerprint,m.ID,now.UTC().UnixNano());err!=nil{return "",0,err}
 if err:=tx.Commit();err!=nil{return "",0,err}

 ms.mu.Lock()
 ms.cacheSetLocked(toCachedMemory(m))
 ms.mu.Unlock()
 ms.logger.Info("Review occurrence stored")
 return m.ID,1,nil
}

// Compile-time check for time.Time timestamp representation.
var _ = time.Time{}
