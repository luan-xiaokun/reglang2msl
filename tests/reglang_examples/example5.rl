// Testcase: contract state
// @return true
rule ContractState
reg contract(tx.to).name=="EIP20" and tx.function=="batchTransfer":
require contract(tx.to).state.balances[tx.from] <= 10000000;
end