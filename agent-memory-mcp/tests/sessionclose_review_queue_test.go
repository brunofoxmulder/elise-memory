package sessionclose

import (
 "go/ast"
 "go/parser"
 "go/token"
 "testing"

 "github.com/ipiton/agent-memory-mcp/internal/memory"
)

// Regression guard: the candidate selection path must exclude pending reviews.
func TestPlanActionsExcludesPendingReviewQueue(t *testing.T) {
 cases := []struct { name string; item *memory.Memory; want bool }{
  {"pending review", &memory.Memory{Metadata: map[string]string{memory.MetadataRecordKind: memory.RecordKindReviewQueueItem}}, true},
  {"ordinary memory", &memory.Memory{Title:"stable knowledge"}, false},
 }
 for _, tc := range cases {
  t.Run(tc.name, func(t *testing.T) {
   if got := memory.IsReviewQueueMemory(tc.item); got != tc.want {
    t.Fatalf("IsReviewQueueMemory = %v, want %v", got, tc.want)
   }
  })
 }
 f, err := parser.ParseFile(token.NewFileSet(), "plan.go", nil, 0)
 if err != nil { t.Fatal(err) }
 var plan *ast.FuncDecl
 for _, decl := range f.Decls {
  if fn, ok := decl.(*ast.FuncDecl); ok && fn.Name.Name == "planActions" { plan = fn; break }
 }
 if plan == nil { t.Fatal("planActions not found") }
 // Verify that the actual exclusion predicate occurs inside the existing-memory loop,
 // rather than merely existing somewhere else in the file.
 found := false
 ast.Inspect(plan.Body, func(n ast.Node) bool {
  loop, ok := n.(*ast.RangeStmt)
  if !ok { return true }
  id, ok := loop.X.(*ast.Ident)
  if !ok || id.Name != "existing" { return true }
  ast.Inspect(loop.Body, func(child ast.Node) bool {
   call, ok := child.(*ast.CallExpr)
   if !ok { return true }
   sel, ok := call.Fun.(*ast.SelectorExpr)
   if !ok || sel.Sel.Name != "IsReviewQueueMemory" { return true }
   pkg, ok := sel.X.(*ast.Ident)
   if ok && pkg.Name == "memory" { found = true }
   return true
  })
  return false
 })
 if !found { t.Fatal("planActions does not filter review queue entries in existing-memory loop") }
}
