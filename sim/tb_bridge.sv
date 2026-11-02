`timescale 1ns/1ps
module tb_bridge;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=1;
 reg [7:0] rx_data=0;reg rx_done=0,rx_error=0;
 wire [7:0] tx_data;wire tx_start;reg tx_busy=0;
 wire qvalid,qready,qwrite,rvalid;
 wire [12:0] qaddr,fail_addr;
 wire [7:0] qdata,rdata,expected,actual;
 wire cfg_done,verify_done,verify_error,busy,csn,sclk,sdio_out,sdio_oe;
 wire overflow,rx_bad;
 reg vio_valid=0;wire vio_ready,vio_rsp;reg [12:0] vio_addr=0;wire [7:0] vio_data;
 tri1 sdio;
 reg corrupt=0;reg [12:0] corrupt_addr=13'h00C;
 reg reserved_high=1;
 wire [31:0] transactions,writes,reads;
 assign sdio=sdio_oe?sdio_out:1'bz;
 bridge_protocol #(.RX_TIMEOUT(40),.OP_TIMEOUT(80000)) protocol(
  .clk(clk),.rst_n(rst_n),.rx_data(rx_data),.rx_done(rx_done),.rx_error(rx_error),
  .tx_data(tx_data),.tx_start(tx_start),.tx_busy(tx_busy),
  .req_valid(qvalid),.req_ready(qready),.req_write(qwrite),.req_addr(qaddr),.req_wdata(qdata),
  .rsp_valid(rvalid),.rsp_rdata(rdata),.status_flags(8'h13),.fail_addr(fail_addr),
  .fail_expected(expected),.fail_actual(actual),.overflow_sticky(overflow),.rx_error_sticky(rx_bad));
 clock_bridge_core #(.SPI_HALF_PERIOD(2),.SETTLE_CYCLES(5)) core(
  .clk(clk),.rst_n(rst_n),.req_valid(qvalid),.req_ready(qready),.req_write(qwrite),
  .req_addr(qaddr),.req_wdata(qdata),.rsp_valid(rvalid),.rsp_rdata(rdata),
  .vio_valid(vio_valid),.vio_ready(vio_ready),.vio_addr(vio_addr),.vio_rsp_valid(vio_rsp),.vio_rdata(vio_data),
  .cfg_done(cfg_done),.verify_done(verify_done),.verify_error(verify_error),
  .fail_addr(fail_addr),.fail_expected(expected),.fail_actual(actual),
  .busy(busy),.spi_csn(csn),.spi_sclk(sclk),.sdio_out(sdio_out),.sdio_oe(sdio_oe),.sdio_in(sdio));
 hmc7044_model model(.rst_n(rst_n),.csn(csn),.sclk(sclk),.sdio(sdio),
  .corrupt(corrupt),.corrupt_addr(corrupt_addr),.reserved_high(reserved_high),.transactions(transactions),.writes(writes),.reads(reads));
 always @(posedge clk) if(rst_n && model.oe && sdio_oe) $fatal(1,"SDIO contention");
 reg [7:0] responses[0:4095];integer response_count=0,tx_cycles=0;
 always @(posedge clk) begin
  if(!rst_n) begin tx_busy<=0;tx_cycles<=0;response_count=0;end
  else if(tx_start && !tx_busy) begin
   responses[response_count]=tx_data;response_count=response_count+1;
   tx_busy<=1;tx_cycles<=3;
  end else if(tx_busy) begin
   if(tx_cycles==0) tx_busy<=0;
   else tx_cycles<=tx_cycles-1;
  end
 end
 function [7:0] crc8(input [7:0] crc,input [7:0] data);
  reg [7:0] c;integer i;begin
   c=crc^data;for(i=0;i<8;i=i+1)c=c[7]?(c<<1)^8'h07:c<<1;crc8=c;
  end
 endfunction
 task byte_in(input [7:0] value);
  begin @(negedge clk);rx_data=value;rx_done=1;@(negedge clk);rx_done=0;repeat(2)@(negedge clk);end
 endtask
 task legacy(input [7:0] cmd,input [15:0] address,input [7:0] value);
  begin byte_in(cmd);byte_in(address[15:8]);byte_in(address[7:0]);byte_in(value);end
 endtask
 task frame(input [7:0] seq,input [7:0] cmd,input [15:0] address,input [7:0] value,input bad);
  reg [7:0] c;begin
   c=0;byte_in(8'hA5);c=crc8(c,8'hA5);byte_in(8'h5A);c=crc8(c,8'h5A);
   byte_in(seq);c=crc8(c,seq);byte_in(cmd);c=crc8(c,cmd);
   byte_in(address[15:8]);c=crc8(c,address[15:8]);byte_in(address[7:0]);c=crc8(c,address[7:0]);
   byte_in(value);c=crc8(c,value);byte_in(bad?(c^8'h01):c);
  end
 endtask
 task wait_bytes(input integer target);
  integer n;begin
   n=0;while(response_count<target && n<100000)begin @(negedge clk);n=n+1;end
   if(response_count!=target)$fatal(1,"Response count: got %0d expected %0d",response_count,target);
   repeat(20)@(negedge clk);
  end
 endtask
 task check_frame(input integer base,input [7:0] seq,input [7:0] status,input [7:0] cmd,input [15:0] addr,input [7:0] value);
  integer j;reg [7:0] c;begin
   if({responses[base],responses[base+1],responses[base+2],responses[base+3],responses[base+4],
       responses[base+5],responses[base+6],responses[base+7]}!={8'h5A,8'hA5,seq,status,cmd,addr,value})
    $fatal(1,"Framed response mismatch at %0d status=%h result=%h",base,responses[base+3],responses[base+7]);
   c=0;for(j=0;j<8;j=j+1)c=crc8(c,responses[base+j]);
   if(c!==responses[base+8])$fatal(1,"Bad response CRC");
  end
 endtask
 task reset_system;
  begin @(negedge clk);rst_n=0;repeat(5)@(negedge clk);rst_n=1;end
 endtask
 integer base,t;
 initial begin
  reset_system();
  // A command arriving during initialization must wait, rather than be lost.
  legacy(1,16'h123,8'h45);
  wait_bytes(4);
  if(!cfg_done || !verify_done || verify_error)$fatal(1,"Good initialization did not pass: cfg=%b done=%b error=%b addr=%h expected=%h actual=%h",cfg_done,verify_done,verify_error,fail_addr,expected,actual);
  reserved_high=0;
  if(writes!=243 || reads!=5)$fatal(1,"Initialization sequence count mismatch");
  if({responses[0],responses[1],responses[2],responses[3]}!==32'h01012345)$fatal(1,"Legacy write response");
  legacy(2,16'h123,0);wait_bytes(8);
  if(responses[7]!==8'h45)$fatal(1,"Legacy read failed");
  frame(8'h10,4,16'h234,8'h96,0);wait_bytes(17);
  check_frame(8,8'h10,0,4,16'h234,8'h96);
  t=transactions;
  frame(8'h11,1,16'h234,8'h11,1);wait_bytes(26);
  check_frame(17,8'h11,1,1,16'h234,0);
  if(transactions!=t)$fatal(1,"Bad CRC reached SPI");
  frame(8'h12,1,16'h2234,8'h11,0);wait_bytes(35);
  check_frame(26,8'h12,4,1,16'h2234,0);
  if(transactions!=t)$fatal(1,"Bad address reached SPI");
  frame(8'h13,8'h7F,0,0,0);wait_bytes(44);
  check_frame(35,8'h13,2,8'h7F,0,0);
  frame(8'h14,3,0,0,0);wait_bytes(53);check_frame(44,8'h14,0,3,0,8'h13);
  // Truncated packet and UART stop-bit error both reset the parser.
  byte_in(8'hA5);byte_in(8'h5A);byte_in(8'hFF);repeat(50)@(negedge clk);
  legacy(2,16'h234,0);wait_bytes(57);if(responses[56]!==8'h96 || !rx_bad)$fatal(1,"Timeout recovery failed");
  byte_in(1);@(negedge clk);rx_error=1;@(negedge clk);rx_error=0;
  legacy(2,16'h123,0);wait_bytes(61);if(responses[60]!==8'h45)$fatal(1,"UART error recovery failed");
  // Four requests while the first SPI operation is busy: payload isolation and FIFO ordering.
  base=response_count;
  frame(8'h20,1,16'h300,8'hAA,0);frame(8'h21,1,16'h301,8'h55,0);
  frame(8'h22,2,16'h300,0,0);frame(8'h23,2,16'h301,0,0);
  wait_bytes(base+36);
  check_frame(base,8'h20,0,1,16'h300,8'hAA);check_frame(base+9,8'h21,0,1,16'h301,8'h55);
  check_frame(base+18,8'h22,0,2,16'h300,8'hAA);check_frame(base+27,8'h23,0,2,16'h301,8'h55);
  // A pending VIO read must never receive a UART response.
  @(negedge clk);vio_addr=13'h123;vio_valid=1;
  wait(vio_ready);@(negedge clk);vio_valid=0;
  frame(8'h24,2,16'h234,0,0);
  wait(vio_rsp);if(vio_data!==8'h45)$fatal(1,"VIO response ownership failed");
  wait_bytes(base+45);check_frame(base+36,8'h24,0,2,16'h234,8'h96);
  if(overflow)$fatal(1,"Unexpected FIFO overflow");
  // Force bus unavailability to exercise the bounded request timeout and recovery.
  base=response_count;
  force core.verify_done=1'b0;
  frame(8'h25,2,16'h123,0,0);wait_bytes(base+9);
  check_frame(base,8'h25,3,2,16'h123,0);
  release core.verify_done;
  frame(8'h26,2,16'h123,0,0);wait_bytes(base+18);
  check_frame(base+9,8'h26,0,2,16'h123,8'h45);
  // Fill the queue with TX blocked; overflow must be sticky, never overwrite old entries.
  base=response_count;
  force tx_busy=1'b1;
  for(t=0;t<7;t=t+1)frame(8'h40+t,3,0,0,0);
  repeat(10)@(negedge clk);
  if(!overflow)$fatal(1,"FIFO overflow was not reported");
  release tx_busy;
  wait_bytes(base+45);
  for(t=0;t<5;t=t+1)check_frame(base+9*t,8'h40+t,0,3,0,8'h13);
  // Fail verification without blocking future diagnostic requests.
  corrupt=1;corrupt_addr=13'h00C;reset_system();wait(verify_done);@(negedge clk);
  if(!cfg_done || !verify_error || fail_addr!=13'h00C || expected!=8'h06 || actual!=8'hF9)
   $fatal(1,"Readback fault not recorded");
  frame(8'h30,3,16'h2,0,0);wait_bytes(9);check_frame(0,8'h30,0,3,16'h2,8'h0C);
  frame(8'h31,4,16'h00C,8'h06,0);wait_bytes(18);check_frame(9,8'h31,5,4,16'h00C,8'hF9);
  wait(uart_tests_done);
  $display("PASS: initialization, masked verification, legacy/framed UART, CRC rejection, address checks, request timeout, parser recovery, FIFO ordering/overflow, VIO arbitration, SDIO timing, fault reporting, UART 8N1 and stop-bit validation");
  $finish;
 end
 initial begin #10000000;$fatal(1,"Simulation watchdog expired");end
 // Exercise the actual UART implementation independently of the byte-level protocol tests.
 reg uart_tests_done=0,uart_start=0,manual_mode=0,manual_pin=1;
 reg [7:0] uart_tx_value=0;
 wire uart_pin,uart_tx_busy,uart_rx_done,uart_rx_error;
 wire [7:0] uart_rx_value;
 integer uart_received=0,uart_errors=0;
 reg [7:0] last_uart_value;
 uart_tx #(.CLK_FREQ(5000000),.BAUD_RATE(115200)) actual_tx(
  .clk(clk),.rst_n(rst_n),.tx_data(uart_tx_value),.tx_start(uart_start),.tx_busy(uart_tx_busy),.tx_pin(uart_pin));
 uart_rx #(.CLK_FREQ(5000000),.BAUD_RATE(115200)) actual_rx(
  .clk(clk),.rst_n(rst_n),.rx_pin(manual_mode?manual_pin:uart_pin),
  .rx_data(uart_rx_value),.rx_done(uart_rx_done),.rx_error(uart_rx_error));
 always @(posedge clk) begin
  if(uart_rx_done)begin uart_received=uart_received+1;last_uart_value=uart_rx_value;end
  if(uart_rx_error)uart_errors=uart_errors+1;
 end
 task uart_send(input [7:0] value);
  begin
   @(negedge clk);uart_tx_value=value;uart_start=1;
   @(negedge clk);uart_start=0;
   wait(uart_tx_busy);wait(!uart_tx_busy);repeat(5)@(negedge clk);
   if(last_uart_value!==value)$fatal(1,"UART loopback mismatch");
  end
 endtask
 integer ub;
 initial begin
  wait(!rst_n);wait(rst_n);repeat(10)@(negedge clk);
  uart_send(8'h00);uart_send(8'hFF);uart_send(8'hA5);uart_send(8'h5A);
  if(uart_received!=4)$fatal(1,"UART receive count");
  manual_mode=1;
  @(negedge clk);manual_pin=0;repeat(43)@(negedge clk);
  for(ub=0;ub<8;ub=ub+1)begin manual_pin=1;repeat(43)@(negedge clk);end
  manual_pin=0;repeat(43)@(negedge clk);manual_pin=1;repeat(100)@(negedge clk);
  if(uart_errors!=1 || uart_received!=4)$fatal(1,"UART invalid stop bit was accepted");
  uart_tests_done=1;
 end
endmodule
