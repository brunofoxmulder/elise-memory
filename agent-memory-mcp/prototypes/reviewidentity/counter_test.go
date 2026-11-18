package reviewidentity

import (
 "context"
 "database/sql"
 "sync"
 "testing"
 "time"

 _ "modernc.org/sqlite"
)

func TestCounterConcurrentOccurrences(t *testing.T){
 db,err:=sql.Open("sqlite","file:review-counter-test?mode=memory&cache=shared")
 if err!=nil{t.Fatal(err)}
 defer db.Close()
 db.SetMaxOpenConns(1) // prototype concurrency: serialize at driver level
 store,err:=NewCounterStore(db);if err!=nil{t.Fatal(err)}
 const n=20
 var wg sync.WaitGroup
 errs:=make(chan error,n)
 for i:=0;i<n;i++{
  wg.Add(1)
  go func(){defer wg.Done();_,err:=store.RecordOccurrence(context.Background(),"fingerprint",time.Now());errs<-err}()
 }
 wg.Wait();close(errs)
 for err:=range errs{if err!=nil{t.Fatal(err)}}
 var got int
 if err:=db.QueryRow("SELECT seen_count FROM prototype_review_occurrences WHERE fingerprint=?", "fingerprint").Scan(&got);err!=nil{t.Fatal(err)}
 if got!=n{t.Fatalf("got %d, want %d",got,n)}
}

func TestCounterSeparateIdentities(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close()
 db.SetMaxOpenConns(1)
 store,err:=NewCounterStore(db);if err!=nil{t.Fatal(err)}
 for _,key:=range []string{"door","fridge","door"}{
  if _,err:=store.RecordOccurrence(context.Background(),key,time.Now());err!=nil{t.Fatal(err)}
 }
 var count int
 if err:=db.QueryRow("SELECT seen_count FROM prototype_review_occurrences WHERE fingerprint='fridge'").Scan(&count);err!=nil{t.Fatal(err)}
 if count!=1{t.Fatalf("fridge count %d, want 1",count)}
 if err:=db.QueryRow("SELECT seen_count FROM prototype_review_occurrences WHERE fingerprint='door'").Scan(&count);err!=nil{t.Fatal(err)}
 if count!=2{t.Fatalf("door count %d, want 2",count)}
}
