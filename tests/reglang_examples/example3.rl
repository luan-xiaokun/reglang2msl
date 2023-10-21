// Testcase: Tx basic info
// @return true
rule TxBasic
reg tx.function=="batchTransfer":
require tx.args._value <= 1000000;
require tx.args._receivers[0] == "0x5929eba30850986de6f93397a86f9b80901896e8";
end