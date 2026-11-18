package reviewidentity

import (
 "context"
 "database/sql"
 "errors"
 "fmt"
 "strings"
 "time"
)

// AtomicReviewStore is an isolated proof of concept for inserting a review
// record and its identity link in the same SQLite transaction. The tables
// are intentionally separate from upstream Agent Memory MCP.
type AtomicReviewStore struct { db *sql.DB }

func NewAtomicReviewStore(db *sql.DB)(*AtomicReviewStore,error){
 statements:=[]string{
 `CREATE TABLE IF NOT EXISTS prototype_review_records (
   memory_id TEXT PRIMARY KEY,
   content TEXT NOT NULL
 )`,
 `CREATE TABLE IF NOT EXISTS prototype_review_events (
   event_id TEXT PRIMARY KEY,
   fingerprint TEXT NOT NULL,
   memory_id TEXT NOT NULL
 )`,
 `CREATE TABLE IF NOT EXISTS prototype_atomic_review_links (
   fingerprint TEXT PRIMARY KEY,
   memory_id TEXT NOT NULL UNIQUE REFERENCES prototype_review_records(memory_id),
   seen_count INTEGER NOT NULL CHECK(seen_count >= 1),
   decision TEXT NOT NULL DEFAULT 'pending',
   last_seen_at TEXT NOT NULL
 )`,
 }
 for _,statement:=range statements{
  if _,err:=db.Exec(statement);err!=nil{return nil,fmt.Errorf("create prototype tables: %w",err)}
 }
 return &AtomicReviewStore{db:db},nil
}

// SaveOccurrence writes the record and identity link together. If the
// fingerprint already exists, its original memory ID and content are kept.
// SQLite serializes competing write transactions; the unique key prevents
// duplicate identities across database connections.
func (s *AtomicReviewStore) SaveOccurrence(ctx context.Context,fingerprint,memoryID,content string,seenAt time.Time)(string,int,error){
 if s==nil||s.db==nil{return "",0,errors.New("atomic store not initialized")}
 if strings.TrimSpace(fingerprint)==""||strings.TrimSpace(memoryID)==""{return "",0,errors.New("fingerprint and memory ID required")}
 if seenAt.IsZero(){return "",0,errors.New("occurrence timestamp required")}
 tx,err:=s.db.BeginTx(ctx,nil)
 if err!=nil{return "",0,fmt.Errorf("begin review transaction: %w",err)}
 defer tx.Rollback()
 // Insert a record only if this fingerprint is not already linked.
 // A duplicate memory ID for a DIFFERENT fingerprint must fail rather
 // than silently link two identities to the same record.
 _,err=tx.ExecContext(ctx,`INSERT INTO prototype_review_records(memory_id,content)
 SELECT ?,? WHERE NOT EXISTS(
 SELECT 1 FROM prototype_atomic_review_links WHERE fingerprint=?
 )`,memoryID,content,fingerprint)
 if err!=nil{return "",0,fmt.Errorf("insert review record: %w",err)}
 var id string
 var count int
 err=tx.QueryRowContext(ctx,`INSERT INTO prototype_atomic_review_links(fingerprint,memory_id,seen_count,last_seen_at)
 VALUES(?,?,1,?)
 ON CONFLICT(fingerprint) DO UPDATE SET
 seen_count=prototype_atomic_review_links.seen_count+1,
 last_seen_at=CASE WHEN excluded.last_seen_at > prototype_atomic_review_links.last_seen_at THEN excluded.last_seen_at ELSE prototype_atomic_review_links.last_seen_at END
 WHERE prototype_atomic_review_links.decision = 'pending'
 RETURNING memory_id,seen_count`,fingerprint,memoryID,seenAt.UTC().Format(time.RFC3339Nano)).Scan(&id,&count)
 if errors.Is(err,sql.ErrNoRows){return "",0,errors.New("review already decided: new verified evidence required")}
 if err!=nil{return "",0,fmt.Errorf("upsert review link: %w",err)}
 if err=tx.Commit();err!=nil{return "",0,fmt.Errorf("commit review transaction: %w",err)}
 return id,count,nil
}

// SaveEvent records a unique source event exactly once. Unlike SaveOccurrence,
// retrying the same event ID does not increase seen_count. The event identity,
// memory row and review link are committed in one SQLite transaction.
func (s *AtomicReviewStore) SaveEvent(ctx context.Context,eventID,fingerprint,memoryID,content string,seenAt time.Time)(string,int,error){
 if s==nil||s.db==nil{return "",0,errors.New("atomic store not initialized")}
 if strings.TrimSpace(eventID)==""||strings.TrimSpace(fingerprint)==""||strings.TrimSpace(memoryID)==""||seenAt.IsZero(){return "",0,errors.New("event identity, fingerprint, memory ID and timestamp required")}
 tx,err:=s.db.BeginTx(ctx,nil)
 if err!=nil{return "",0,err}
 defer tx.Rollback()
 result,err:=tx.ExecContext(ctx,`INSERT INTO prototype_review_events(event_id,fingerprint,memory_id)
 VALUES(?,?,?) ON CONFLICT(event_id) DO NOTHING`,eventID,fingerprint,memoryID)
 if err!=nil{return "",0,fmt.Errorf("insert review event: %w",err)}
 affected,err:=result.RowsAffected()
 if err!=nil{return "",0,err}
 if affected==0 {
  var existingFingerprint string
  if err:=tx.QueryRowContext(ctx,`SELECT fingerprint FROM prototype_review_events WHERE event_id=?`,eventID).Scan(&existingFingerprint);err!=nil{return "",0,err}
  if existingFingerprint!=fingerprint{return "",0,errors.New("event ID reused for a different proposal")}
  var id string
  var count int
  if err:=tx.QueryRowContext(ctx,`SELECT memory_id,seen_count FROM prototype_atomic_review_links WHERE fingerprint=?`,fingerprint).Scan(&id,&count);err!=nil{return "",0,err}
  if err:=tx.Commit();err!=nil{return "",0,err}
  return id,count,nil
 }
 _,err=tx.ExecContext(ctx,`INSERT INTO prototype_review_records(memory_id,content)
 SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM prototype_atomic_review_links WHERE fingerprint=?)`,memoryID,content,fingerprint)
 if err!=nil{return "",0,err}
 var id string
 var count int
 err=tx.QueryRowContext(ctx,`INSERT INTO prototype_atomic_review_links(fingerprint,memory_id,seen_count,last_seen_at)
 VALUES(?,?,1,?) ON CONFLICT(fingerprint) DO UPDATE SET
 seen_count=prototype_atomic_review_links.seen_count+1,
 last_seen_at=CASE WHEN excluded.last_seen_at > prototype_atomic_review_links.last_seen_at THEN excluded.last_seen_at ELSE prototype_atomic_review_links.last_seen_at END
 WHERE prototype_atomic_review_links.decision='pending'
 RETURNING memory_id,seen_count`,fingerprint,memoryID,seenAt.UTC().Format(time.RFC3339Nano)).Scan(&id,&count)
 if errors.Is(err,sql.ErrNoRows){return "",0,errors.New("review already decided")}
 if err!=nil{return "",0,err}
 if err:=tx.Commit();err!=nil{return "",0,err}
 return id,count,nil
}
