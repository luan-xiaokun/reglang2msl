knowledgebase black
knowledge blacklist = ["0xBEeFbeefbEefbeEFbeEfbEEfBEeFbeEfBeEfBeef"];
end

rule CheckTransfer
reg contract(tx.to).name=="EIP20" and tx.function=="transfer":
require tx.args._value <= 1000000;
prohibit tx.from in knowledgebase(black).blacklist or tx.args._to in knowledgebase(black).blacklist;
end