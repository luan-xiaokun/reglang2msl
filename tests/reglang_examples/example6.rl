// Testcase: knowledgebase
// @return false
knowledgebase black
knowledge blacklist = ["0x84C7768aC1Cd6d07FCA1e2BC4C3551510F6E4ABC", "0x5929eba30850986de6f93397a86f9b80901896e8"];
blacklist.del("0x5929eba30850986de6f93397a86f9b80901896e8");
blacklist.add(["0x84C7768aC1Cd6d07FCA1e2BC4C3551510F6E4ABC", "0xD1AaC31f34Ca1e5e64Ac9710DC8a59EEFabC1474"]);
end

rule CheckBlacklistWithKnowledge
reg contract(tx.to).name=="EIP20" and tx.function=="batchTransfer":
require knowledgebase(black).blacklist[0] == "0x84C7768aC1Cd6d07FCA1e2BC4C3551510F6E4ABC";
prohibit tx.from in knowledgebase(black).blacklist;
end
