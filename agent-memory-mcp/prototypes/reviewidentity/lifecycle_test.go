package reviewidentity

import "testing"

func TestReopenPolicy(t *testing.T) {
 cases:=[]struct{
  name string
  status ReviewDecision
  evidence Evidence
  want bool
 }{
  {"pending unchanged",Pending,Evidence{},false},
  {"pending new source",Pending,Evidence{NewRelevantSource:true},false},
  {"deferred new source",Deferred,Evidence{NewRelevantSource:true},false},
  {"resolved no change",Resolved,Evidence{},false},
  {"resolved content changed",Resolved,Evidence{TargetContentChanged:true},true},
  {"dismissed new source",Dismissed,Evidence{NewRelevantSource:true},true},
  {"dismissed unchanged",Dismissed,Evidence{},false},
  {"unknown",ReviewDecision("unknown"),Evidence{NewRelevantSource:true},false},
 }
 for _,tc:=range cases{
  t.Run(tc.name,func(t *testing.T){
   if got:=MayCreateAfterDecision(tc.status,tc.evidence);got!=tc.want{
    t.Fatalf("got %v, want %v",got,tc.want)
   }
  })
 }
}
