// Testcase: Basic data type
// @return true
rule BasicType
reg 1 == 1:
require 1 < 50 and 2 < 50;
require 1 <= 1;
require 2 > 1;
require 2 >= 1;
prohibit 1 != 1;
require true or false;
prohibit false;
require 1+1 == 2;
require 2-1 == 1;
require 2*2 == 4;
require 2/2 == 1;
require 3/2 == 1;
require 4%2 == 0;
require 2^3 == 8;
require 10+"0xa"+"10" == 30;
require 10 == "10";
require 10 == "0xa";
require "10" == "0xa";
require "abc" == "ABC";
end