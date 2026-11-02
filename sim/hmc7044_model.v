`timescale 1ns/1ps
// Digital SPI register-file model, not a PLL/analog timing model.
module hmc7044_model(
 input wire rst_n,input wire csn,input wire sclk,inout wire sdio,
 input wire corrupt,input wire [12:0] corrupt_addr,input wire reserved_high,
 output reg [31:0] transactions,output reg [31:0] writes,output reg [31:0] reads
);
 reg [7:0] memory[0:8191];
 reg [15:0] header;
 reg [7:0] data;
 reg [12:0] address;
 reg reading,oe,out_bit;
 integer bits,i;
 assign sdio=oe ? out_bit : 1'bz;
 always @(negedge rst_n) begin
  for(i=0;i<8192;i=i+1) memory[i]=0;
  transactions=0;writes=0;reads=0;
 end
 always @(negedge csn) begin bits=0;header=0;data=0;reading=0;oe=0;end
 always @(posedge sclk) if(!csn) begin
  if(bits<16) begin
   header={header[14:0],sdio};
   if(bits==0) reading=sdio;
   if(bits==15) address=header[12:0];
  end else if(!reading) data={data[6:0],sdio};
  bits=bits+1;
  if(bits>24) $fatal(1,"Too many SPI clocks");
 end
 always @(negedge sclk or posedge csn) begin
  if(csn) oe=0;
  else if(reading && bits>=16 && bits<24) begin
   oe=1;
   out_bit=memory[address][23-bits];
   if(reserved_high && address>=13'h00A && address<=13'h00E && bits<19) out_bit=1;
   if(corrupt && address==corrupt_addr) out_bit=~out_bit;
  end
 end
 always @(posedge csn) if(rst_n && bits>0) begin
  if(bits!=24) $fatal(1,"SPI transaction length %0d, expected 24",bits);
  transactions=transactions+1;
  if(reading) reads=reads+1;
  else begin writes=writes+1; memory[address]=data;end
 end
endmodule
