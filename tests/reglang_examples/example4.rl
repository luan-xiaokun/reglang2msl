// Testcase: Tx readset and writeset
// @return true
rule TxSet
reg tx.function=="batchTransfer":
require tx.readset(tx.to).balances[tx.from] <= 10000000;
require tx.writeset(tx.to).balances[tx.from] <= 10000000;
end