`timescale 1ns/1ps
// Original 242-entry programming sequence; verify only stable input-buffer bits.
module hmc7044_init #(parameter SETTLE_CYCLES=5000)(
 input wire clk, input wire rst_n,
 output wire req_valid, input wire req_ready, output wire req_write,
 output wire [12:0] req_addr, output wire [7:0] req_wdata,
 input wire rsp_valid, input wire [7:0] rsp_rdata,
 output reg cfg_done, output reg verify_done, output reg verify_error,
 output reg [12:0] fail_addr, output reg [7:0] fail_expected, output reg [7:0] fail_actual
);
 localparam SEND=0, WAIT_RSP=1, SETTLE=2, FINISH=3;
 localparam TW=(SETTLE_CYCLES<2)?1:$clog2(SETTLE_CYCLES);
 reg [1:0] state;
 reg [7:0] table_index;
 reg [2:0] verify_index;
 reg verifying;
 reg [TW-1:0] timer;
 reg [19:0] table_word;
 wire [7:0] expected = (verify_index==1 || verify_index==4) ? 8'h07 : 8'h06;
 assign req_valid = state==SEND;
 assign req_write = !verifying;
 assign req_addr = verifying ? (13'h00A + {10'b0,verify_index}) : {1'b0,table_word[19:8]};
 assign req_wdata = table_word[7:0];
 always @* begin
  table_word=20'h00000;
  case(table_index)

               12'h000:  table_word = 20'h00001;
                    12'h001:  table_word = 20'h00000;
                    12'h002:  table_word = 20'h00140;
                    12'h003:  table_word = 20'h00200;
                    12'h004:  table_word = 20'h00337;
                    12'h005:  table_word = 20'h00411;
                    12'h006:  table_word = 20'h0054F;
                    12'h007:  table_word = 20'h00600;
                    12'h008:  table_word = 20'h00700;
                    12'h009:  table_word = 20'h00901;
                    12'h00A:  table_word = 20'h00A06;
                    12'h00B:  table_word = 20'h00B07;
                    12'h00C:  table_word = 20'h00C06;
                    12'h00D:  table_word = 20'h00D06;
                    12'h00E:  table_word = 20'h00E07;
                    12'h00F:  table_word = 20'h014E1;
                    12'h010:  table_word = 20'h01503;
                    12'h011:  table_word = 20'h0160C;
                    12'h012:  table_word = 20'h01700;
                    12'h013:  table_word = 20'h01804;
                    12'h014:  table_word = 20'h01900;
                    12'h015:  table_word = 20'h01A08;
                    12'h016:  table_word = 20'h01B18;
                    12'h017:  table_word = 20'h01C01;
                    12'h018:  table_word = 20'h01D01;
                    12'h019:  table_word = 20'h01E01;
                    12'h01A:  table_word = 20'h01F01;
                    12'h01B:  table_word = 20'h02001;
                    12'h01C:  table_word = 20'h02101;
                    12'h01D:  table_word = 20'h02200;
                    12'h01E:  table_word = 20'h0267D;
                    12'h01F:  table_word = 20'h02700;
                    12'h020:  table_word = 20'h0280F;
                    12'h021:  table_word = 20'h0290C;
                    12'h022:  table_word = 20'h02A00;
                    12'h023:  table_word = 20'h03101;
                    12'h024:  table_word = 20'h03201;
                    12'h025:  table_word = 20'h03305;
                    12'h026:  table_word = 20'h03400;
                    12'h027:  table_word = 20'h03560;
                    12'h028:  table_word = 20'h03600;
                    12'h029:  table_word = 20'h0370F;
                    12'h02A:  table_word = 20'h03818;
                    12'h02B:  table_word = 20'h03900;
                    12'h02C:  table_word = 20'h03A00;
                    12'h02D:  table_word = 20'h03B00;
                    12'h02E:  table_word = 20'h04600;
                    12'h02F:  table_word = 20'h04700;
                    12'h030:  table_word = 20'h04808;
                    12'h031:  table_word = 20'h04910;
                    12'h032:  table_word = 20'h05037;
                    12'h033:  table_word = 20'h05133;
                    12'h034:  table_word = 20'h05200;
                    12'h035:  table_word = 20'h05300;
                    12'h036:  table_word = 20'h05403;
                    12'h037:  table_word = 20'h05A00;
                    12'h038:  table_word = 20'h05B06;
                    12'h039:  table_word = 20'h05CC0;
                    12'h03A:  table_word = 20'h05D03;
                    12'h03B:  table_word = 20'h06400;
                    12'h03C:  table_word = 20'h06500;
                    12'h03D:  table_word = 20'h07000;
                    12'h03E:  table_word = 20'h07110;
                    12'h03F:  table_word = 20'h07808;
                    12'h040:  table_word = 20'h07909;
                    12'h041:  table_word = 20'h07A0A;
                    12'h042:  table_word = 20'h07B01;
                    12'h043:  table_word = 20'h07C0C;
                    12'h044:  table_word = 20'h07D0D;
                    12'h045:  table_word = 20'h07E0E;
                    12'h046:  table_word = 20'h0820F;
                    12'h047:  table_word = 20'h08310;
                    12'h048:  table_word = 20'h08411;
                    12'h049:  table_word = 20'h08500;
                    12'h04A:  table_word = 20'h08600;
                    12'h04B:  table_word = 20'h08C02;
                    12'h04C:  table_word = 20'h08D03;
                    12'h04D:  table_word = 20'h08E04;
                    12'h04E:  table_word = 20'h08F05;
                    12'h04F:  table_word = 20'h09106;
                    12'h050:  table_word = 20'h09600;
                    12'h051:  table_word = 20'h09700;
                    12'h052:  table_word = 20'h09800;
                    12'h053:  table_word = 20'h09900;
                    12'h054:  table_word = 20'h09A00;
                    12'h055:  table_word = 20'h09BAA;
                    12'h056:  table_word = 20'h09CAA;
                    12'h057:  table_word = 20'h09DAA;
                    12'h058:  table_word = 20'h09EAA;
                    12'h059:  table_word = 20'h09F4D;
                    12'h05A:  table_word = 20'h0A0DF;
                    12'h05B:  table_word = 20'h0A197;
                    12'h05C:  table_word = 20'h0A203;
                    12'h05D:  table_word = 20'h0A300;
                    12'h05E:  table_word = 20'h0A400;
                    12'h05F:  table_word = 20'h0A506;
                    12'h060:  table_word = 20'h0A61C;
                    12'h061:  table_word = 20'h0A700;
                    12'h062:  table_word = 20'h0A806;
                    12'h063:  table_word = 20'h0A900;
                    12'h064:  table_word = 20'h0AB00;
                    12'h065:  table_word = 20'h0AC20;
                    12'h066:  table_word = 20'h0AD00;
                    12'h067:  table_word = 20'h0AE08;
                    12'h068:  table_word = 20'h0AF50;
                    12'h069:  table_word = 20'h0B004;
                    12'h06A:  table_word = 20'h0B10D;
                    12'h06B:  table_word = 20'h0B200;
                    12'h06C:  table_word = 20'h0B300;
                    12'h06D:  table_word = 20'h0B500;
                    12'h06E:  table_word = 20'h0B600;
                    12'h06F:  table_word = 20'h0B700;
                    12'h070:  table_word = 20'h0B800;
                    12'h071:  table_word = 20'h0C8F3;
                    12'h072:  table_word = 20'h0C93C;
                    12'h073:  table_word = 20'h0CA00;
                    12'h074:  table_word = 20'h0CB00;
                    12'h075:  table_word = 20'h0CC00;
                    12'h076:  table_word = 20'h0CD00;
                    12'h077:  table_word = 20'h0CE00;
                    12'h078:  table_word = 20'h0CF00;
                    12'h079:  table_word = 20'h0D011;
                    12'h07A:  table_word = 20'h0D2FC;
                    12'h07B:  table_word = 20'h0D3E0;
                    12'h07C:  table_word = 20'h0D401;
                    12'h07D:  table_word = 20'h0D500;
                    12'h07E:  table_word = 20'h0D600;
                    12'h07F:  table_word = 20'h0D700;
                    12'h080:  table_word = 20'h0D800;
                    12'h081:  table_word = 20'h0D900;
                    12'h082:  table_word = 20'h0DA28;
                    12'h083:  table_word = 20'h0DCF2;
                    12'h084:  table_word = 20'h0DD08;
                    12'h085:  table_word = 20'h0DE00;
                    12'h086:  table_word = 20'h0DF00;
                    12'h087:  table_word = 20'h0E000;
                    12'h088:  table_word = 20'h0E100;
                    12'h089:  table_word = 20'h0E200;
                    12'h08A:  table_word = 20'h0E300;
                    12'h08B:  table_word = 20'h0E401;
                    12'h08C:  table_word = 20'h0E6FC;
                    12'h08D:  table_word = 20'h0E700;
                    12'h08E:  table_word = 20'h0E801;
                    12'h08F:  table_word = 20'h0E900;
                    12'h090:  table_word = 20'h0EA00;
                    12'h091:  table_word = 20'h0EB00;
                    12'h092:  table_word = 20'h0EC00;
                    12'h093:  table_word = 20'h0ED00;
                    12'h094:  table_word = 20'h0EE30;
                    12'h095:  table_word = 20'h0F0F2;
                    12'h096:  table_word = 20'h0F102;
                    12'h097:  table_word = 20'h0F200;
                    12'h098:  table_word = 20'h0F300;
                    12'h099:  table_word = 20'h0F400;
                    12'h09A:  table_word = 20'h0F500;
                    12'h09B:  table_word = 20'h0F600;
                    12'h09C:  table_word = 20'h0F700;
                    12'h09D:  table_word = 20'h0F801;
                    12'h09E:  table_word = 20'h0FAFC;
                    12'h09F:  table_word = 20'h0FB00;
                    12'h0A0:  table_word = 20'h0FC01;
                    12'h0A1:  table_word = 20'h0FD00;
                    12'h0A2:  table_word = 20'h0FE00;
                    12'h0A3:  table_word = 20'h0FF00;
                    12'h0A4:  table_word = 20'h10000;
                    12'h0A5:  table_word = 20'h10100;
                    12'h0A6:  table_word = 20'h10230;
                    12'h0A7:  table_word = 20'h104F2;
                    12'h0A8:  table_word = 20'h10502;
                    12'h0A9:  table_word = 20'h10600;
                    12'h0AA:  table_word = 20'h10700;
                    12'h0AB:  table_word = 20'h10800;
                    12'h0AC:  table_word = 20'h10900;
                    12'h0AD:  table_word = 20'h10A00;
                    12'h0AE:  table_word = 20'h10B00;
                    12'h0AF:  table_word = 20'h10C01;
                    12'h0B0:  table_word = 20'h10EFC;
                    12'h0B1:  table_word = 20'h10F00;
                    12'h0B2:  table_word = 20'h11001;
                    12'h0B3:  table_word = 20'h11100;
                    12'h0B4:  table_word = 20'h11200;
                    12'h0B5:  table_word = 20'h11300;
                    12'h0B6:  table_word = 20'h11400;
                    12'h0B7:  table_word = 20'h11500;
                    12'h0B8:  table_word = 20'h11630;
                    12'h0B9:  table_word = 20'h118F3;
                    12'h0BA:  table_word = 20'h1193C;
                    12'h0BB:  table_word = 20'h11A00;
                    12'h0BC:  table_word = 20'h11B00;
                    12'h0BD:  table_word = 20'h11C00;
                    12'h0BE:  table_word = 20'h11D00;
                    12'h0BF:  table_word = 20'h11E00;
                    12'h0C0:  table_word = 20'h11F00;
                    12'h0C1:  table_word = 20'h12009;
                    12'h0C2:  table_word = 20'h122FC;
                    12'h0C3:  table_word = 20'h12300;
                    12'h0C4:  table_word = 20'h12401;
                    12'h0C5:  table_word = 20'h12500;
                    12'h0C6:  table_word = 20'h12600;
                    12'h0C7:  table_word = 20'h12700;
                    12'h0C8:  table_word = 20'h12800;
                    12'h0C9:  table_word = 20'h12900;
                    12'h0CA:  table_word = 20'h12A30;
                    12'h0CB:  table_word = 20'h12CF2;
                    12'h0CC:  table_word = 20'h12D02;
                    12'h0CD:  table_word = 20'h12E00;
                    12'h0CE:  table_word = 20'h12F00;
                    12'h0CF:  table_word = 20'h13000;
                    12'h0D0:  table_word = 20'h13100;
                    12'h0D1:  table_word = 20'h13200;
                    12'h0D2:  table_word = 20'h13300;
                    12'h0D3:  table_word = 20'h13401;
                    12'h0D4:  table_word = 20'h136FC;
                    12'h0D5:  table_word = 20'h13700;
                    12'h0D6:  table_word = 20'h13801;
                    12'h0D7:  table_word = 20'h13900;
                    12'h0D8:  table_word = 20'h13A00;
                    12'h0D9:  table_word = 20'h13B00;
                    12'h0DA:  table_word = 20'h13C00;
                    12'h0DB:  table_word = 20'h13D00;
                    12'h0DC:  table_word = 20'h13E30;
                    12'h0DD:  table_word = 20'h140F2;
                    12'h0DE:  table_word = 20'h14110;
                    12'h0DF:  table_word = 20'h14200;
                    12'h0E0:  table_word = 20'h14300;
                    12'h0E1:  table_word = 20'h14400;
                    12'h0E2:  table_word = 20'h14500;
                    12'h0E3:  table_word = 20'h14600;
                    12'h0E4:  table_word = 20'h14700;
                    12'h0E5:  table_word = 20'h14801;
                    12'h0E6:  table_word = 20'h14AFC;
                    12'h0E7:  table_word = 20'h14B00;
                    12'h0E8:  table_word = 20'h14C01;
                    12'h0E9:  table_word = 20'h14D00;
                    12'h0EA:  table_word = 20'h14E00;
                    12'h0EB:  table_word = 20'h14F00;
                    12'h0EC:  table_word = 20'h15000;
                    12'h0ED:  table_word = 20'h15100;
                    12'h0EE:  table_word = 20'h15230;
                    12'h0EF:  table_word = 20'h00162;
                    12'h0F0:  table_word = 20'h00000;
                    12'h0F1:  table_word = 20'h00160;
                default: table_word = 20'h00000; 
            
  endcase
 end
 always @(posedge clk) begin
  if(!rst_n) begin
   state<=SEND; table_index<=0; verify_index<=0; verifying<=0; timer<=0;
   cfg_done<=0; verify_done<=0; verify_error<=0;
   fail_addr<=0; fail_expected<=0; fail_actual<=0;
  end else case(state)
   SEND: if(req_ready) state<=WAIT_RSP;
   WAIT_RSP: if(rsp_valid) begin
    if(!verifying) begin
     if(table_index==241) begin cfg_done<=1; timer<=0; state<=SETTLE; end
     else begin table_index<=table_index+1'b1; state<=SEND; end
    end else begin
     if((rsp_rdata & 8'h1F)!=(expected & 8'h1F)) begin
      verify_error<=1;
      if(!verify_error) begin fail_addr<=req_addr; fail_expected<=expected; fail_actual<=rsp_rdata; end
     end
     if(verify_index==4) begin verify_done<=1; state<=FINISH; end
     else begin verify_index<=verify_index+1'b1; state<=SEND; end
    end
   end
   SETTLE: if(timer==SETTLE_CYCLES-1) begin verifying<=1; state<=SEND; end
           else timer<=timer+1'b1;
   FINISH: state<=FINISH;
   default: state<=FINISH;
  endcase
 end
endmodule
