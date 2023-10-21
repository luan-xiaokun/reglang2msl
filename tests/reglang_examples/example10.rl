knowledgebase string
knowledge string_add_num = ("1" + 0) + (1 + "0");
knowledge string_mul_num = ("1" * 2) % (2 / "1");
end

rule StringArithRule
reg true:
require 2 * ("0xff" + "0") > 1;
require (1 + "0xff") * "0" == "0";
require "0x2" ^ "0x4" > 0;
require tx.args.lst["0"] == "foo";
end

rule TxStateAndContractState
reg true:
require tx.readset(tx.to).foo == contract(tx.to).state.bar;
end