// Conflict
// @return Conflict
rule TxBasic1
reg tx.function=="batchTransfer":
require tx.args._value > 100000; //
require tx.args._senders == "Alice";
end
