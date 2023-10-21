// Testcase: empty rule and multiple rules
// @return true
rule EmptyRule
reg true:
end

rule MultiRule
reg true:
require true;
prohibit false;
end

