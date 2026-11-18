package reviewidentity

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "errors"
 "strings"
)

// SourceEvent is an immutable occurrence identity provided by the originating
// system. Retry attempts must reuse the SAME source event ID. A timestamp
// generated at retry time is not an acceptable event identity.
type SourceEvent struct {
 SourceSystem string `json:"source_system"`
 SourceRecordID string `json:"source_record_id"`
 ActionID string `json:"action_id"`
}

func EventKey(e SourceEvent) (string,error) {
 e.SourceSystem=strings.TrimSpace(e.SourceSystem)
 e.SourceRecordID=strings.TrimSpace(e.SourceRecordID)
 e.ActionID=strings.TrimSpace(e.ActionID)
 if e.SourceSystem==""||e.SourceRecordID==""||e.ActionID=="" {
  return "",errors.New("source system, immutable record ID and action ID required")
 }
 b,_:=json.Marshal(e)
 sum:=sha256.Sum256(append([]byte("maison-cognitive/review-event/v1\x00"),b...))
 return hex.EncodeToString(sum[:]),nil
}
