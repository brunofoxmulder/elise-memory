package reviewidentity

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "strings"
)

// SubjectKey identifies a review subject independently of mutable titles
// and candidate content. A separate domain prevents accidental interchange
// with proposal fingerprints, including when the proposal body is empty.
func SubjectKey(p Proposal) string {
 p.TargetTitle = ""
 p.CandidateTitle = ""
 p.CandidateContent = ""
 p.Project = strings.TrimSpace(p.Project)
 p.Context = strings.TrimSpace(p.Context)
 p.Service = strings.TrimSpace(p.Service)
 p.Entity = strings.TrimSpace(p.Entity)
 p.EngineeringType = strings.TrimSpace(p.EngineeringType)
 p.ActionKind = strings.TrimSpace(p.ActionKind)
 p.TargetMemoryID = strings.TrimSpace(p.TargetMemoryID)
 b, _ := json.Marshal(p)
 sum := sha256.Sum256(append([]byte("maison-cognitive/review-subject/v1\x00"), b...))
 return hex.EncodeToString(sum[:])
}

// EvidenceChanged only identifies a content difference within the same
// subject. It is never sufficient evidence for reopening a decision.
func EvidenceChanged(before, after Proposal) bool {
 if SubjectKey(before) != SubjectKey(after) { return false }
 return strings.TrimSpace(before.CandidateContent) != strings.TrimSpace(after.CandidateContent)
}
