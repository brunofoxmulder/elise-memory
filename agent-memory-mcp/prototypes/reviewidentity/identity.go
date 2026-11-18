package reviewidentity

// Isolated design prototype for CH-REVIEWQ-20261118 correctif B.
// This package is NOT wired into the HAOS add-on. No production behavior changes.
import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "strings"
)

// Proposal identifies the complete scope of a review-queue action.
// Content must be the FULL candidate text, never the 220-character display excerpt.
type Proposal struct {
 Project string `json:"project"`
 Context string `json:"context"`
 Service string `json:"service"`
 Entity string `json:"entity"`
 EngineeringType string `json:"engineering_type"`
 ActionKind string `json:"action_kind"`
 TargetMemoryID string `json:"target_memory_id"`
 TargetTitle string `json:"target_title"`
 CandidateTitle string `json:"candidate_title"`
 CandidateContent string `json:"candidate_content"`
}

// Fingerprint is deterministic and domain-separated. It is an identity candidate,
// not yet a proven substitute for the source application's lifecycle policy.
func Fingerprint(p Proposal) string {
 p.Project = strings.TrimSpace(p.Project)
 p.Context = strings.TrimSpace(p.Context)
 p.Service = strings.TrimSpace(p.Service)
 p.Entity = strings.TrimSpace(p.Entity)
 p.EngineeringType = strings.TrimSpace(p.EngineeringType)
 p.ActionKind = strings.TrimSpace(p.ActionKind)
 p.TargetMemoryID = strings.TrimSpace(p.TargetMemoryID)
 p.TargetTitle = strings.TrimSpace(p.TargetTitle)
 p.CandidateTitle = strings.TrimSpace(p.CandidateTitle)
 p.CandidateContent = strings.TrimSpace(p.CandidateContent)
 b, _ := json.Marshal(p) // struct with string-only fields: Marshal cannot fail.
 sum := sha256.Sum256(append([]byte("maison-cognitive/review-proposal/v1\x00"), b...))
 return hex.EncodeToString(sum[:])
}
