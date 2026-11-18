package reviewidentity

import (
 "context"
 "database/sql"
 "errors"
 "fmt"
 "time"
)

// ReviewLinkStore prototypes a transactional association between a review
// record and its stable identity. This is a separate experimental schema:
// it is NOT an Agent Memory MCP migration and cannot affect HAOS.
type ReviewLinkStore struct { db *sql.DB }

func NewReviewLinkStore(db *sql.DB)(*ReviewLinkStore,error){
 _,err:=db.Exec(`CREATE TABLE IF NOT EXISTS prototype_review_links (
  fingerprint TEXT PRIMARY KEY,
  memory_id TEXT NOT NULL UNIQUE,
  seen_count INTEGER NOT NULL DEFAULT 1 CHECK(seen_count >= 1),
  last_seen_at TEXT NOT NULL
 )`)
 if err!=nil{return nil,fmt.Errorf("create prototype review links: %w",err)}
 return &ReviewLinkStore{db:db},nil
}

// AttachOrIncrement atomically creates a review identity link or increments
// the existing one. The supplied memoryID is used ONLY on initial insertion.
// This proof of concept does not create the memory row; the real integration
// must insert both records in ONE transaction.
func (s *ReviewLinkStore) AttachOrIncrement(ctx context.Context,fingerprint,memoryID string,seenAt time.Time)(string,int,error){
 if s==nil||s.db==nil{return "",0,errors.New("review link store not initialized")}
 if fingerprint==""||memoryID==""{return "",0,errors.New("fingerprint and memory ID required")}
 var id string
 var count int
 err:=s.db.QueryRowContext(ctx,`INSERT INTO prototype_review_links(fingerprint,memory_id,seen_count,last_seen_at)
 VALUES(?,?,1,?)
 ON CONFLICT(fingerprint) DO UPDATE SET
 seen_count=prototype_review_links.seen_count+1,
 last_seen_at=excluded.last_seen_at
 RETURNING memory_id,seen_count`,fingerprint,memoryID,seenAt.UTC().Format(time.RFC3339Nano)).Scan(&id,&count)
 if err!=nil{return "",0,fmt.Errorf("attach review identity: %w",err)}
 return id,count,nil
}
