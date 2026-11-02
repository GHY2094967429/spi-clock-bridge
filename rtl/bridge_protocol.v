`timescale 1ns/1ps
// Legacy 4-byte commands plus CRC-8 framed commands; four queued requests.
module bridge_protocol #(parameter RX_TIMEOUT=100000, parameter OP_TIMEOUT=500000)(
 input wire clk,input wire rst_n,input wire [7:0] rx_data,input wire rx_done,input wire rx_error,
 output reg [7:0] tx_data,output reg tx_start,input wire tx_busy,
 output wire req_valid,input wire req_ready,output wire req_write,
 output wire [12:0] req_addr,output wire [7:0] req_wdata,
 input wire rsp_valid,input wire [7:0] rsp_rdata,
 input wire [7:0] status_flags,input wire [12:0] fail_addr,
 input wire [7:0] fail_expected,input wire [7:0] fail_actual,
 output reg overflow_sticky,output reg rx_error_sticky
);
 function [7:0] crc8;
  input [7:0] crc; input [7:0] data;
  reg [7:0] c; integer b;
  begin c=crc^data; for(b=0;b<8;b=b+1) c=c[7] ? (c<<1)^8'h07 : c<<1; crc8=c; end
 endfunction
 localparam RTW=(RX_TIMEOUT<2)?1:$clog2(RX_TIMEOUT);
 localparam OTW=(OP_TIMEOUT<2)?1:$clog2(OP_TIMEOUT);
 // Parser: 0 idle, 1 second sync, 2 framed body, 3 legacy body.
 reg [1:0] parser;
 reg [2:0] rx_index;
 reg [RTW-1:0] rx_timer;
 reg [7:0] p_seq,p_cmd,p_hi,p_lo,p_data,p_crc;
 reg packet_valid;
 reg [48:0] packet;
 always @(posedge clk) begin
  if(!rst_n) begin
   parser<=0; rx_index<=0; rx_timer<=0; p_seq<=0;p_cmd<=0;p_hi<=0;p_lo<=0;p_data<=0;p_crc<=0;
   packet_valid<=0;packet<=0;rx_error_sticky<=0;
  end else begin
   packet_valid<=0;
   if(rx_error) begin parser<=0;rx_timer<=0;rx_error_sticky<=1; end
   else if(rx_done) begin
    rx_timer<=0;
    case(parser)
     0: if(rx_data==8'hA5) parser<=1;
        else if(rx_data>=1 && rx_data<=4) begin p_cmd<=rx_data; rx_index<=1; parser<=3; end
     1: if(rx_data==8'h5A) begin parser<=2;rx_index<=2;p_crc<=crc8(crc8(0,8'hA5),8'h5A); end
        else if(rx_data!=8'hA5) parser<=0;
     2: begin
      if(rx_index!=7) p_crc<=crc8(p_crc,rx_data);
      case(rx_index)
       2:p_seq<=rx_data;
       3:p_cmd<=rx_data;
       4:p_hi<=rx_data;
       5:p_lo<=rx_data;
       6:p_data<=rx_data;
       7:begin
        packet<={1'b1,p_seq,p_cmd,p_hi,p_lo,p_data,((rx_data==p_crc)?8'h00:8'h01)};
        packet_valid<=1; parser<=0;
       end
      endcase
      rx_index<=rx_index+1'b1;
     end
     3: begin
      case(rx_index)
       1:p_hi<=rx_data;
       2:p_lo<=rx_data;
       3:begin packet<={1'b0,8'h00,p_cmd,p_hi,p_lo,rx_data,8'h00};packet_valid<=1;parser<=0;end
      endcase
      rx_index<=rx_index+1'b1;
     end
    endcase
   end else if(parser!=0) begin
    if(rx_timer==RX_TIMEOUT-1) begin parser<=0;rx_timer<=0;rx_error_sticky<=1;end
    else rx_timer<=rx_timer+1'b1;
   end
  end
 end
 // FIFO accepts a new descriptor even on the same cycle as a full-queue pop.
 reg [48:0] queue[0:3];
 reg [1:0] wr_ptr,rd_ptr;
 reg [2:0] count;
 localparam IDLE=0,DISPATCH=1,REQUEST=2,WAIT_RSP=3,SEND=4,TX_START=5,TX_DONE=6;
 reg [2:0] state;
 wire pop=(state==IDLE && count!=0);
 wire push=packet_valid && (count<4 || pop);
 always @(posedge clk) begin
  if(!rst_n) begin wr_ptr<=0;rd_ptr<=0;count<=0;overflow_sticky<=0;end
  else begin
   if(packet_valid && !push) overflow_sticky<=1;
   if(push) begin queue[wr_ptr]<=packet;wr_ptr<=wr_ptr+1'b1;end
   if(pop) rd_ptr<=rd_ptr+1'b1;
   case({push,pop})
    2'b10:count<=count+1'b1;
    2'b01:count<=count-1'b1;
    default:count<=count;
   endcase
  end
 end
 reg framed;
 reg [7:0] seq,cmd,addr_hi,addr_lo,wdata,result,status;
 reg verify_phase;
 reg [OTW-1:0] op_timer;
 reg [3:0] tx_index;
 reg [7:0] tx_crc;
 reg [7:0] byte_out;
 assign req_valid=(state==REQUEST);
 assign req_write=(cmd==1 || cmd==4) && !verify_phase;
 assign req_addr={addr_hi[4:0],addr_lo};
 assign req_wdata=wdata;
 always @* begin
  byte_out=0;
  if(framed) case(tx_index)
   0:byte_out=8'h5A; 1:byte_out=8'hA5; 2:byte_out=seq;
   3:byte_out=status; 4:byte_out=cmd; 5:byte_out=addr_hi;
   6:byte_out=addr_lo;7:byte_out=result;8:byte_out=tx_crc;
   default:byte_out=0;
  endcase
  else case(tx_index)
   0:byte_out=cmd;1:byte_out=addr_hi;2:byte_out=addr_lo;
   3:byte_out=(status==0)?result:8'hEE;
   default:byte_out=0;
  endcase
 end
 always @(posedge clk) begin
  if(!rst_n) begin
   state<=IDLE;framed<=0;seq<=0;cmd<=0;addr_hi<=0;addr_lo<=0;wdata<=0;result<=0;status<=0;
   verify_phase<=0;op_timer<=0;tx_index<=0;tx_crc<=0;tx_data<=0;tx_start<=0;
  end else begin
   tx_start<=0;
   case(state)
    IDLE: if(pop) begin
     {framed,seq,cmd,addr_hi,addr_lo,wdata,status}<=queue[rd_ptr];
     tx_index<=0;tx_crc<=0;verify_phase<=0;op_timer<=0;result<=0;state<=DISPATCH;
    end
    DISPATCH: begin
     if(status!=0) state<=SEND;
     else if(cmd==3) begin
      case({addr_hi,addr_lo})
       16'h0000:result<=status_flags;
       16'h0001:result<={3'b0,fail_addr[12:8]};
       16'h0002:result<=fail_addr[7:0];
       16'h0003:result<=fail_expected;
       16'h0004:result<=fail_actual;
       16'h0005:result<=8'h20;
       default:begin status<=8'h04; result<=0;end
      endcase
      state<=SEND;
     end else if(cmd!=1 && cmd!=2 && cmd!=4) begin status<=8'h02;state<=SEND;end
     else if(addr_hi[7:5]!=0) begin status<=8'h04;state<=SEND;end
     else state<=REQUEST;
    end
    REQUEST: if(req_ready) begin state<=WAIT_RSP;op_timer<=0;end
             else if(op_timer==OP_TIMEOUT-1) begin status<=8'h03;state<=SEND;end
             else op_timer<=op_timer+1'b1;
    WAIT_RSP: if(rsp_valid) begin
      op_timer<=0;
      if(cmd==4 && !verify_phase) begin verify_phase<=1;state<=REQUEST;end
      else begin
       result<=req_write ? wdata : rsp_rdata;
       if(cmd==4 && rsp_rdata!=wdata) status<=8'h05;
       state<=SEND;
      end
     end else if(op_timer==OP_TIMEOUT-1) begin status<=8'h03;state<=SEND;end
     else op_timer<=op_timer+1'b1;
    SEND: if(!tx_busy) begin
     tx_data<=byte_out;tx_start<=1;
     if(framed && tx_index<8) tx_crc<=crc8(tx_crc,byte_out);
     state<=TX_START;
    end
    TX_START: if(tx_busy) state<=TX_DONE;
    TX_DONE: if(!tx_busy) begin
     if(tx_index==(framed?8:3)) state<=IDLE;
     else begin tx_index<=tx_index+1'b1;state<=SEND;end
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
