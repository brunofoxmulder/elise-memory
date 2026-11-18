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

// MayCreateAfterDecision is a pure policy prototype. Deferred remains
// unresolved and must be handled by the queue, not silently reopened.
func MayCreateAfterDecision(status ReviewDecision, evidence Evidence) bool {
 switch status {
 case Pending, Deferred:
  return false
 case Resolved, Dismissed:
  return evidence.TargetContentChanged || evidence.NewRelevantSource
 default:
  return false
 }
}
