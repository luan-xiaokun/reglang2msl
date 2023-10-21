// Testcase: Tx Internal Functions
// @return true
knowledgebase black
knowledge blacklist = ["0x84C7768aC1Cd6d07FCA1e2BC4C3551510F6E4ABC", "0xD1AaC31f34Ca1e5e64Ac9710DC8a59EEFabC1474"];
end

knowledgebase white
knowledge whitelist = ["0x5929EBA30850986dE6F93397A86f9B80901896e8", "0xAb8483F64d9C6d1EcF9b849Ae677dD3315835cb2"];
end

rule TestInternalFunc
reg contract(tx.to).name=="EIP20" and tx.function=="batchTransfer":
require length(knowledgebase(black).blacklist) >= 2;
require length(tx.args._receivers) <= 100;
require count(1==1, 2==2, 1==2) >= 2;
require at_least(2, tx.args._receivers in knowledgebase(white).whitelist);
require at_most(0, tx.args._receivers in knowledgebase(black).blacklist);
prohibit any_item(tx.args._receivers in knowledgebase(black).blacklist);
require all_items(tx.args._receivers in knowledgebase(white).whitelist);
require at_least(1, knowledgebase(black).blacklist == "0x84C7768aC1Cd6d07FCA1e2BC4C3551510F6E4ABC");
end
