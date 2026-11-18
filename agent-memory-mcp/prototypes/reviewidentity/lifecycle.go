package reviewidentity

// ReviewDecision represents the prior review lifecycle without modifying it.
type ReviewDecision string

const (
 Pending ReviewDecision = "pending"
 Resolved ReviewDecision = "resolved"
 Dismissed ReviewDecision = "dismissed"
 Deferred ReviewDecision = "deferred"
)

// Evidence describes a change after the original decision.
// Merely changing verification timestamps is deliberately insufficient.
type Evidence struct {
 TargetContentChanged bool
 NewRelevantSource bool
}

// MayCreateAfterDecision is a legacy compatibility guard. Unverified boolean
// flags must NEVER authorize reopening. Use MayReopenWithVerifiedEvidence
// after the integration has independently checked the source.
func MayCreateAfterDecision(status ReviewDecision, evidence Evidence) bool {
 return false
}
