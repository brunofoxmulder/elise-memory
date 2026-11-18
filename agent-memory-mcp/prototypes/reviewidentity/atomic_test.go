package reviewidentity

import (
 "context"
 "database/sql"
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
