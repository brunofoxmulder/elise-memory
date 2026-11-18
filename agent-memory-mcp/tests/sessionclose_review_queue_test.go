package sessionclose

import (
 "context"
 "path/filepath"
 "testing"

 "github.com/ipiton/agent-memory-mcp/internal/memory"
 "go.uber.org/zap"
)

// Regression: actual planActions must never link to an unvalidated review record.
func TestPlanActionsExcludesPendingReviewQueue(t *testing.T) {
 ctx := context.Background()
 store, err := memory.NewStore(filepath.Join(t.TempDir(), "review-regression.db"), nil, zap.NewNop())
 if err != nil { t.Fatal(err) }
 summary := memory.SessionSummary{Context: "review-regression"}
 candidate := &extractedCandidate{memory: &memory.Memory{
  Title: "Heating automation", Content: "Heating automation decisions",
  Context: summary.Context, Type: memory.TypeSemantic,
 }}
 pending := &memory.Memory{
  Title: candidate.memory.Title, Content: candidate.memory.Content,
  Context: summary.Context, Type: memory.TypeSemantic, Importance: 0.5,
  Metadata: map[string]string{memory.MetadataRecordKind: memory.RecordKindReviewQueueItem},
 }
 if err := store.Store(ctx, pending); err != nil { t.Fatal(err) }
 svc := New(store)
 actions, linked, err := svc.planActions(ctx, summary, []*extractedCandidate{candidate})
 if err != nil { t.Fatal(err) }
 if len(actions) != 1 { t.Fatalf("actions: got %d, want 1", len(actions)) }
 if actions[0].TargetMemoryID != "" || len(linked) != 0 {
  t.Fatalf("pending review was selected as target: target=%q linked=%v", actions[0].TargetMemoryID, linked)
 }
 // A genuine memory with the same content remains eligible for linking.
 valid := &memory.Memory{
  Title: candidate.memory.Title, Content: candidate.memory.Content,
  Context: summary.Context, Type: memory.TypeSemantic, Importance: 0.5,
 }
 if err := store.Store(ctx, valid); err != nil { t.Fatal(err) }
 actions, linked, err = svc.planActions(ctx, summary, []*extractedCandidate{candidate})
 if err != nil { t.Fatal(err) }
 if len(actions) != 1 || actions[0].TargetMemoryID != valid.ID {
  t.Fatalf("valid memory was not selected: actions=%+v valid=%q", actions, valid.ID)
 }
 if len(linked) != 1 || linked[0] != valid.ID {
  t.Fatalf("expected only valid memory linked: %v", linked)
 }
}
