package reviewidentity

import (
 "strings"
 "testing"
)

func TestFingerprintStable(t *testing.T) {
 p:=Proposal{Project:"Maison Cognitive",Context:"security",Entity:"sensor.leak_fridge",ActionKind:"update",CandidateContent:"inspect"}
 if Fingerprint(p)!=Fingerprint(p) { t.Fatal("unstable fingerprint") }
 p2:=p; p2.CandidateContent=" inspect "
 if Fingerprint(p)!=Fingerprint(p2) { t.Fatal("surrounding whitespace should be ignored") }
}

func TestFingerprintDistinguishesScope(t *testing.T) {
 p:=Proposal{Project:"Maison Cognitive",Context:"security",Entity:"sensor.leak_door",ActionKind:"update",CandidateContent:"water leak"}
 q:=p; q.Entity="sensor.leak_fridge"
 r:=p; r.Entity="sensor.leak_freezer"
 if Fingerprint(p)==Fingerprint(q)||Fingerprint(p)==Fingerprint(r)||Fingerprint(q)==Fingerprint(r){t.Fatal("distinct entities collapsed")}
}

func TestFingerprintUsesFullContent(t *testing.T) {
 p:=Proposal{Context:"backups",ActionKind:"update",CandidateContent:strings.Repeat("x",220)+"old"}
 q:=p; q.CandidateContent=strings.Repeat("x",220)+"new"
 if Fingerprint(p)==Fingerprint(q){t.Fatal("content truncated at 220 characters")}
}

func TestFingerprintSeparatesTargetAndMeaning(t *testing.T) {
 p:=Proposal{Context:"energy",ActionKind:"update",TargetMemoryID:"one",CandidateContent:"timeouts increased"}
 q:=p; q.TargetMemoryID="two"
 r:=p; r.CandidateContent="timeouts resolved"
 if Fingerprint(p)==Fingerprint(q)||Fingerprint(p)==Fingerprint(r){t.Fatal("distinct targets or facts collapsed")}
}
