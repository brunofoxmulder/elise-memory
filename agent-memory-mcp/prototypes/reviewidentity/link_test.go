package reviewidentity

import (
 "context"
 "database/sql"
 "testing"
 "time"

 _ "modernc.org/sqlite"
)

func TestReviewLinkPreservesOriginalMemoryID(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close()
 db.SetMaxOpenConns(1)
 store,err:=NewReviewLinkStore(db);if err!=nil{t.Fatal(err)}
 id,count,err:=store.AttachOrIncrement(context.Background(),"same-proposal","original-id",time.Now())
 if err!=nil||id!="original-id"||count!=1{t.Fatalf("initial link %q %d %v",id,count,err)}
 id,count,err=store.AttachOrIncrement(context.Background(),"same-proposal","new-throwaway-id",time.Now())
 if err!=nil||id!="original-id"||count!=2{t.Fatalf("duplicate link %q %d %v",id,count,err)}
}

func TestReviewLinkRejectsSameMemoryForDifferentIdentity(t *testing.T){
 db,err:=sql.Open("sqlite",":memory:");if err!=nil{t.Fatal(err)}
 defer db.Close()
 db.SetMaxOpenConns(1)
 store,err:=NewReviewLinkStore(db);if err!=nil{t.Fatal(err)}
 if _,_,err:=store.AttachOrIncrement(context.Background(),"proposal-A","same-memory",time.Now());err!=nil{t.Fatal(err)}
 if _,_,err:=store.AttachOrIncrement(context.Background(),"proposal-B","same-memory",time.Now());err==nil{
  t.Fatal("one memory ID must not be assigned to distinct proposal identities")
 }
}
