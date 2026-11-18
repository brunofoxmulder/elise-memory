package reviewidentity

import "testing"

func TestVerifiedEvidenceGate(t *testing.T){
 good:=VerifiedEvidence{SourceID:"ha-history:2026-11-18",ObservedAt:"2026-11-18T17:00:00Z",TargetVersionBefore:"v1",TargetVersionAfter:"v2",Verified:true,Relevant:true}
 cases:=[]struct{name string;status ReviewDecision;change func(*VerifiedEvidence);want bool}{
  {"resolved with verified change",Resolved,nil,true},
  {"dismissed with verified change",Dismissed,nil,true},
  {"pending cannot reopen",Pending,nil,false},
  {"deferred cannot reopen",Deferred,nil,false},
  {"no source",Resolved,func(e *VerifiedEvidence){e.SourceID=""},false},
  {"no timestamp",Resolved,func(e *VerifiedEvidence){e.ObservedAt=""},false},
  {"invalid timestamp",Resolved,func(e *VerifiedEvidence){e.ObservedAt="yesterday"},false},
  {"missing baseline",Resolved,func(e *VerifiedEvidence){e.TargetVersionBefore=""},false},
  {"no version change",Resolved,func(e *VerifiedEvidence){e.TargetVersionAfter="v1"},false},
  {"unverified",Resolved,func(e *VerifiedEvidence){e.Verified=false},false},
  {"irrelevant",Resolved,func(e *VerifiedEvidence){e.Relevant=false},false},
 }
 for _,tc:=range cases{t.Run(tc.name,func(t *testing.T){
  e:=good
  if tc.change!=nil{tc.change(&e)}
  if got:=MayReopenWithVerifiedEvidence(tc.status,e);got!=tc.want{t.Fatalf("got %t want %t",got,tc.want)}
 })}
}
