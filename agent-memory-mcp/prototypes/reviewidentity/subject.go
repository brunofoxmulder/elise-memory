package reviewidentity

import "strings"

// SubjectKey identifies the review subject independently from the evidence
// payload. It is NOT a replacement for Fingerprint: the latter distinguishes
// materially different candidate contents on the same subject.
func SubjectKey(p Proposal) string {
 p.TargetTitle = ""
 p.CandidateTitle = ""
 p.CandidateContent = ""
 return Fingerprint(p)
}

// EvidenceChanged is a conservative, local comparison of two proposals.
// A changed candidate body is a candidate signal, NOT verified new evidence.
// Source validation and relevance must occur before reopening a decision.
func EvidenceChanged(before, after Proposal) bool {
 if SubjectKey(before) != SubjectKey(after) { return false }
 return strings.TrimSpace(before.CandidateContent) != strings.TrimSpace(after.CandidateContent)
}
