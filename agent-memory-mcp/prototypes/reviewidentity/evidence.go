package reviewidentity

import (
 "errors"
 "strings"
 "time"
)

// VerifiedEvidence is a caller-attested record. This prototype does not
// independently verify source authenticity; the integration must do so.
type VerifiedEvidence struct {
 SourceID string
 ObservedAt string // RFC3339, supplied by the evidence source
 TargetVersionBefore string
 TargetVersionAfter string
 Relevant bool
 Verified bool
}

// MayReopenWithVerifiedEvidence requires evidence that is attributable,
// timestamped, verified and relevant, in addition to a substantive change.
// It never reopens pending or deferred review decisions.
func MayReopenWithVerifiedEvidence(status ReviewDecision, evidence VerifiedEvidence) bool {
 if status != Resolved && status != Dismissed {return false}
 if err:=ValidateVerifiedEvidence(evidence);err!=nil{return false}
 return strings.TrimSpace(evidence.TargetVersionBefore)!=strings.TrimSpace(evidence.TargetVersionAfter)
}

// ValidateVerifiedEvidence performs syntactic validation only. It cannot
// establish the truth of the source or the relevance of the change.
func ValidateVerifiedEvidence(e VerifiedEvidence) error {
 if strings.TrimSpace(e.SourceID)=="" {return errors.New("missing evidence source")}
 if strings.TrimSpace(e.ObservedAt)=="" {return errors.New("missing evidence timestamp")}
 if _,err:=time.Parse(time.RFC3339,e.ObservedAt);err!=nil{return errors.New("invalid RFC3339 evidence timestamp")}
 if strings.TrimSpace(e.TargetVersionBefore)=="" || strings.TrimSpace(e.TargetVersionAfter)=="" {return errors.New("missing target version")}
 if !e.Verified || !e.Relevant {return errors.New("evidence not verified and relevant")}
 return nil
}
