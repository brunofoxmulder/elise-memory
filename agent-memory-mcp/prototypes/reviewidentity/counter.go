package reviewidentity

import (
 "context"
 "database/sql"
 "errors"
 "fmt"
 "time"
)

// CounterStore is an isolated SQLite proof of concept. It is NOT the upstream
// memories schema and MUST NOT be deployed as an add-on migration.
type CounterStore struct { db *sql.DB }

// NewCounterStore creates a standalone prototype table on a caller-owned DB.
// SQLite's UNIQUE key and UPSERT provide concurrency safety across connections.
func NewCounterStore(db *sql.DB) (*CounterStore,error) {
 _,err:=db.Exec(`CREATE TABLE IF NOT EXISTS prototype_review_occurrences (
   fingerprint TEXT PRIMARY KEY,
   seen_count INTEGER NOT NULL DEFAULT 1 CHECK(seen_count >= 1),
   last_seen_at TEXT NOT NULL
 )`)
 if err!=nil{return nil,fmt.Errorf("create prototype review counter: %w",err)}
 return &CounterStore{db:db},nil
}

// RecordOccurrence increments one proposal exactly once per successful call.
// The caller is responsible for stable, source-verified fingerprint inputs.
func (s *CounterStore) RecordOccurrence(ctx context.Context,fingerprint string,seenAt time.Time)(int,error){
 if s==nil||s.db==nil{return 0,errors.New("counter store is not initialized")}
 if fingerprint=="" {return 0,errors.New("empty fingerprint")}
 var count int
 err:=s.db.QueryRowContext(ctx,`INSERT INTO prototype_review_occurrences(fingerprint,seen_count,last_seen_at)
 VALUES (?,1,?)
 ON CONFLICT(fingerprint) DO UPDATE SET
 seen_count=prototype_review_occurrences.seen_count+1,
 last_seen_at=excluded.last_seen_at
 RETURNING seen_count`,fingerprint,seenAt.UTC().Format(time.RFC3339Nano)).Scan(&count)
 if err!=nil{return 0,fmt.Errorf("record review occurrence: %w",err)}
 return count,nil
}
