package reviewidentity

import "testing"

func TestSubjectKeySeparatesScopeFromEvidence(t *testing.T){
 base:=Proposal{Project:"Maison Cognitive",Service:"HA",Entity:"sensor.freezer",TargetMemoryID:"memory-1",CandidateContent:"alarm threshold 5 min"}
 changed:=base
 changed.CandidateContent="alarm threshold 10 min"
 if SubjectKey(base)!=SubjectKey(changed){t.Fatal("same subject should have same key")}
 if Fingerprint(base)==Fingerprint(changed){t.Fatal("distinct evidence should have distinct fingerprints")}
 if !EvidenceChanged(base,changed){t.Fatal("changed candidate text should be detectable")}
 other:=base
 other.Entity="sensor.door"
 if SubjectKey(base)==SubjectKey(other){t.Fatal("different entity must not share subject key")}
 if EvidenceChanged(base,other){t.Fatal("different subjects must not be treated as evidence revision")}
}

func TestSubjectKeyDoesNotTreatSessionMetadataAsIdentity(t *testing.T){
 p:=Proposal{Project:"Maison Cognitive",Service:"HA",TargetMemoryID:"memory-1",CandidateContent:"same fact"}
 // Proposal deliberately contains no session boundary or raw summary ID.
 if SubjectKey(p)==""{t.Fatal("subject key must not be empty")}
 if SubjectKey(p)!=SubjectKey(p){t.Fatal("subject key must be deterministic")}
}

func TestSubjectKeyIgnoresPresentationTitles(t *testing.T){
 first:=Proposal{Project:"Maison Cognitive",Entity:"sensor.freezer",TargetMemoryID:"m1",TargetTitle:"Freezer safety",CandidateTitle:"Initial proposal",CandidateContent:"threshold 5 minutes"}
 second:=first
 second.TargetTitle="Sécurité congélateur"
 second.CandidateTitle="Reformulation"
 if SubjectKey(first)!=SubjectKey(second){t.Fatal("presentation-only title changes altered subject identity")}
 if Fingerprint(first)==Fingerprint(second){t.Fatal("full proposal fingerprints should still preserve original text differences")}
}

func TestSubjectAndProposalDomainsAreDistinct(t *testing.T) {
 p:=Proposal{Project:"Maison Cognitive",Context:"review",Service:"memory",ActionKind:"create"}
 if SubjectKey(p)==Fingerprint(p){t.Fatal("subject and proposal domains collided")}
 if SubjectKey(p)!=SubjectKey(p){t.Fatal("subject key not deterministic")}
}
