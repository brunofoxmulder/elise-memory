package reviewidentity

import "testing"

func TestEventKeyStableAcrossRetries(t *testing.T){
 source:=SourceEvent{SourceSystem:"session-close",SourceRecordID:"session-42",ActionID:"action-1"}
 a,err:=EventKey(source);if err!=nil{t.Fatal(err)}
 b,err:=EventKey(source);if err!=nil||a!=b{t.Fatal("retry changed source event identity")}
 source.ActionID="action-2"
 c,err:=EventKey(source);if err!=nil||a==c{t.Fatal("distinct action has same event identity")}
 source.ActionID=""
 if _,err:=EventKey(source);err==nil{t.Fatal("missing action ID accepted")}
}
