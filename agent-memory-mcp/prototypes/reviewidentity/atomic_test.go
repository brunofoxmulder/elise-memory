package reviewidentity

import (
 "context"
 "database/sql"
 "fmt"
 "path/filepath"
 "sync"
 "testing"
 "time"

 _ "modernc.org/sqlite"
)

func TestAtomicReviewRecordAndLink(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 id,n,err:=store.SaveOccurrence(context.Background(),"fingerprint","first","original",time.Now())
 if err!=nil||id!="first"||n!=1{t.Fatalf("first: %q %d %v",id,n,err)}
 id,n,err=store.SaveOccurrence(context.Background(),"fingerprint","second","replacement",time.Now())
 if err!=nil||id!="first"||n!=2{t.Fatalf("repeat: %q %d %v",id,n,err)}
 var rows int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&rows);err!=nil{t.Fatal(err)}
 if rows!=1{t.Fatalf("expected one record, got %d",rows)}
 var content string
 if err:=db.QueryRow("SELECT content FROM prototype_review_records WHERE memory_id='first'").Scan(&content);err!=nil{t.Fatal(err)}
 if content!="original"{t.Fatalf("existing content overwritten: %q",content)}
}

func TestAtomicReviewRollbackOnLinkFailure(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 if _,err:=db.Exec(`CREATE TRIGGER fail_review_link BEFORE INSERT ON prototype_atomic_review_links
 BEGIN SELECT RAISE(ABORT,'injected link failure'); END`);err!=nil{t.Fatal(err)}
 if _,_,err:=store.SaveOccurrence(context.Background(),"f","new-record","body",time.Now());err==nil{t.Fatal("expected failure")}
 var rows int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&rows);err!=nil{t.Fatal(err)}
 if rows!=0{t.Fatalf("transaction left %d orphan records",rows)}
}

func TestAtomicReviewConcurrentConnections(t *testing.T){
 path:=filepath.Join(t.TempDir(),"atomic.sqlite")
 db1,err:=sql.Open("sqlite",path);if err!=nil{t.Fatal(err)}
 defer db1.Close()
 db2,err:=sql.Open("sqlite",path);if err!=nil{t.Fatal(err)}
 defer db2.Close()
 for _,db:=range []*sql.DB{db1,db2}{
  db.SetMaxOpenConns(1)
  if _,err:=db.Exec("PRAGMA busy_timeout=10000");err!=nil{t.Fatal(err)}
  if _,err:=db.Exec("PRAGMA journal_mode=WAL");err!=nil{t.Fatal(err)}
 }
 a,err:=NewAtomicReviewStore(db1);if err!=nil{t.Fatal(err)}
 b,err:=NewAtomicReviewStore(db2);if err!=nil{t.Fatal(err)}
 const n=30
 var wg sync.WaitGroup
 errs:=make(chan error,n)
 for i:=0;i<n;i++{
  wg.Add(1)
  target:=a
  if i%2!=0{target=b}
  go func(i int,store *AtomicReviewStore){
   defer wg.Done()
   _,_,err:=store.SaveOccurrence(context.Background(),"one-proposal",fmt.Sprintf("candidate-%d",i),"content",time.Now())
   errs<-err
  }(i,target)
 }
 wg.Wait();close(errs)
 for err:=range errs{if err!=nil{t.Fatal(err)}}
 var records,links,count int
 if err:=db1.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&records);err!=nil{t.Fatal(err)}
 if err:=db1.QueryRow("SELECT count(*) FROM prototype_atomic_review_links").Scan(&links);err!=nil{t.Fatal(err)}
 if err:=db1.QueryRow("SELECT seen_count FROM prototype_atomic_review_links WHERE fingerprint='one-proposal'").Scan(&count);err!=nil{t.Fatal(err)}
 if records!=1||links!=1||count!=n{t.Fatalf("records=%d links=%d count=%d, want 1/1/%d",records,links,count,n)}
}

func TestAtomicReviewRejectsMemoryIDCollision(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 if _,_,err:=store.SaveOccurrence(context.Background(),"first-fingerprint","same-id","first body",time.Now());err!=nil{t.Fatal(err)}
 if _,_,err:=store.SaveOccurrence(context.Background(),"different-fingerprint","same-id","second body",time.Now());err==nil{
  t.Fatal("different fingerprint unexpectedly reused existing memory ID")
 }
 var links int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_atomic_review_links").Scan(&links);err!=nil{t.Fatal(err)}
 if links!=1{t.Fatalf("collision created %d links, want 1",links)}
 var content string
 if err:=db.QueryRow("SELECT content FROM prototype_review_records WHERE memory_id='same-id'").Scan(&content);err!=nil{t.Fatal(err)}
 if content!="first body"{t.Fatalf("collision altered original content: %q",content)}
}

func TestAtomicReviewPreservesDecisions(t *testing.T){
 for _,decision:=range []string{"resolved","dismissed","deferred"}{
  t.Run(decision,func(t *testing.T){
   db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
   defer db.Close();db.SetMaxOpenConns(1)
   store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
   if _,_,err:=store.SaveOccurrence(context.Background(),"fingerprint","original","body",time.Now());err!=nil{t.Fatal(err)}
   if _,err:=db.Exec("UPDATE prototype_atomic_review_links SET decision=? WHERE fingerprint='fingerprint'",decision);err!=nil{t.Fatal(err)}
   if _,_,err:=store.SaveOccurrence(context.Background(),"fingerprint","candidate","changed",time.Now());err==nil{
    t.Fatal("decided proposal should not be incremented or reopened without verified new evidence")
   }
   var count int
   var status string
   if err:=db.QueryRow("SELECT seen_count,decision FROM prototype_atomic_review_links WHERE fingerprint='fingerprint'").Scan(&count,&status);err!=nil{t.Fatal(err)}
   if count!=1||status!=decision{t.Fatalf("decision mutated: count=%d status=%s",count,status)}
   var records int
   if err:=db.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&records);err!=nil{t.Fatal(err)}
   if records!=1{t.Fatalf("rollback left %d records",records)}
  })
 }
}

func TestAtomicReviewOutOfOrderOccurrences(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 recent:=time.Date(2026,11,18,17,0,0,0,time.UTC)
 older:=recent.Add(-2*time.Hour)
 if _,_,err:=store.SaveOccurrence(context.Background(),"f","m1","body",recent);err!=nil{t.Fatal(err)}
 if _,n,err:=store.SaveOccurrence(context.Background(),"f","m2","other",older);err!=nil||n!=2{t.Fatalf("repeat: n=%d err=%v",n,err)}
 var last string
 if err:=db.QueryRow("SELECT last_seen_at FROM prototype_atomic_review_links WHERE fingerprint='f'").Scan(&last);err!=nil{t.Fatal(err)}
 if last!=recent.Format(time.RFC3339Nano){t.Fatalf("timestamp regressed: %q",last)}
}

func TestAtomicReviewRejectsInvalidInputsWithoutWrites(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 cases:=[]struct{fingerprint,id string;at time.Time}{
  {" ","m1",time.Now()},
  {"fingerprint"," ",time.Now()},
  {"fingerprint","m1",time.Time{}},
 }
 for _,tc:=range cases{
  if _,_,err:=store.SaveOccurrence(context.Background(),tc.fingerprint,tc.id,"body",tc.at);err==nil{t.Fatal("invalid input accepted")}
 }
 var n int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&n);err!=nil{t.Fatal(err)}
 if n!=0{t.Fatalf("invalid inputs wrote %d records",n)}
}

func TestSaveEventIdempotentReplay(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 at:=time.Now()
 id,n,err:=store.SaveEvent(context.Background(),"event-1","fingerprint","m1","original",at)
 if err!=nil||id!="m1"||n!=1{t.Fatalf("first: %s %d %v",id,n,err)}
 id,n,err=store.SaveEvent(context.Background(),"event-1","fingerprint","m2","changed",at)
 if err!=nil||id!="m1"||n!=1{t.Fatalf("replay: %s %d %v",id,n,err)}
 id,n,err=store.SaveEvent(context.Background(),"event-2","fingerprint","m3","changed",at)
 if err!=nil||id!="m1"||n!=2{t.Fatalf("new event: %s %d %v",id,n,err)}
 if _,_,err:=store.SaveEvent(context.Background(),"event-1","other","m4","body",at);err==nil{t.Fatal("event collision not rejected")}
 var records,events int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&records);err!=nil{t.Fatal(err)}
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_events").Scan(&events);err!=nil{t.Fatal(err)}
 if records!=1||events!=2{t.Fatalf("records=%d events=%d",records,events)}
}
func TestSaveEventRollbackOnDecidedReview(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close();db.SetMaxOpenConns(1)
 store,err:=NewAtomicReviewStore(db);if err!=nil{t.Fatal(err)}
 if _,_,err:=store.SaveEvent(context.Background(),"event-1","fingerprint","m1","body",time.Now());err!=nil{t.Fatal(err)}
 if _,err:=db.Exec("UPDATE prototype_atomic_review_links SET decision='resolved' WHERE fingerprint='fingerprint'");err!=nil{t.Fatal(err)}
 if _,_,err:=store.SaveEvent(context.Background(),"event-2","fingerprint","m2","new",time.Now());err==nil{t.Fatal("resolved review accepted new event")}
 var events int
 if err:=db.QueryRow("SELECT count(*) FROM prototype_review_events").Scan(&events);err!=nil{t.Fatal(err)}
 if events!=1{t.Fatalf("failed event was committed: %d",events)}
}

func TestSaveEventConcurrentReplayAcrossConnections(t *testing.T){
 path:=filepath.Join(t.TempDir(),"events.sqlite")
 db1,err:=sql.Open("sqlite",path);if err!=nil{t.Fatal(err)}
 defer db1.Close()
 db2,err:=sql.Open("sqlite",path);if err!=nil{t.Fatal(err)}
 defer db2.Close()
 for _,db:=range []*sql.DB{db1,db2}{
  db.SetMaxOpenConns(1)
  if _,err:=db.Exec("PRAGMA busy_timeout=10000");err!=nil{t.Fatal(err)}
  if _,err:=db.Exec("PRAGMA journal_mode=WAL");err!=nil{t.Fatal(err)}
 }
 a,err:=NewAtomicReviewStore(db1);if err!=nil{t.Fatal(err)}
 b,err:=NewAtomicReviewStore(db2);if err!=nil{t.Fatal(err)}
 const workers=24
 errs:=make(chan error,workers)
 var wg sync.WaitGroup
 for i:=0;i<workers;i++{
  wg.Add(1)
  go func(i int){
   defer wg.Done()
   store:=a
   if i%2==1{store=b}
   _,n,err:=store.SaveEvent(context.Background(),"same-source-event","same-fingerprint",fmt.Sprintf("m-%d",i),"body",time.Now())
   if err==nil&&n!=1{err=fmt.Errorf("replayed event counted %d times",n)}
   errs<-err
  }(i)
 }
 wg.Wait();close(errs)
 for err:=range errs{if err!=nil{t.Fatal(err)}}
 var records,events,count int
 if err:=db1.QueryRow("SELECT count(*) FROM prototype_review_records").Scan(&records);err!=nil{t.Fatal(err)}
 if err:=db1.QueryRow("SELECT count(*) FROM prototype_review_events").Scan(&events);err!=nil{t.Fatal(err)}
 if err:=db1.QueryRow("SELECT seen_count FROM prototype_atomic_review_links WHERE fingerprint='same-fingerprint'").Scan(&count);err!=nil{t.Fatal(err)}
 if records!=1||events!=1||count!=1{t.Fatalf("records=%d events=%d count=%d; want 1/1/1",records,events,count)}
}
