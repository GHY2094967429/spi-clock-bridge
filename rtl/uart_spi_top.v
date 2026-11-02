`timescale 1ns/1ps
// Board wrapper. Business logic can instead instantiate clock_bridge_core directly.
module uart_spi_top(
 input wire sys_clk_p,input wire sys_clk_n,
 input wire uart_top_input,output wire uart_top_output,
 output wire spi_clk,output wire spi_csn,inout wire spi_io,
 output wire hmc7044_rst,output wire [3:0] led,
 input wire hmc7044_gpio1,output wire fmc_led
);
 wire clk,locked,rst,rst_n;
 clk_wiz_0 clocking(.clk_out1(clk),.reset(1'b0),.locked(locked),.clk_in1_p(sys_clk_p),.clk_in1_n(sys_clk_n));
 proc_sys_reset_0 reset_gen(.slowest_sync_clk(clk),.ext_reset_in(1'b0),.aux_reset_in(1'b0),
  .mb_debug_sys_rst(1'b0),.dcm_locked(locked),.mb_reset(),.bus_struct_reset(),
  .peripheral_reset(rst),.interconnect_aresetn(),.peripheral_aresetn(rst_n));
 assign hmc7044_rst=rst;
 (* ASYNC_REG="TRUE" *) reg [1:0] lock_sync;
 reg [23:0] heartbeat;
 always @(posedge clk) begin
  if(!rst_n) begin lock_sync<=0;heartbeat<=0;end
  else begin lock_sync<={lock_sync[0],hmc7044_gpio1};heartbeat<=heartbeat+1'b1;end
 end
 assign fmc_led=lock_sync[1];
 wire [7:0] rx_data,tx_data;
 wire rx_done,rx_error,tx_start,tx_busy;
 uart_rx #(.CLK_FREQ(5000000),.BAUD_RATE(115200)) rx(
  .clk(clk),.rst_n(rst_n),.rx_pin(uart_top_input),.rx_data(rx_data),.rx_done(rx_done),.rx_error(rx_error));
 uart_tx #(.CLK_FREQ(5000000),.BAUD_RATE(115200)) tx(
  .clk(clk),.rst_n(rst_n),.tx_data(tx_data),.tx_start(tx_start),.tx_busy(tx_busy),.tx_pin(uart_top_output));
 wire req_valid,req_ready,req_write,rsp_valid;
 wire [12:0] req_addr,fail_addr;
 wire [7:0] req_wdata,rsp_rdata,fail_expected,fail_actual;
 wire cfg_done,verify_done,verify_error,busy,overflow_sticky,rx_error_sticky;
 wire [7:0] flags={rx_error_sticky,overflow_sticky,busy,lock_sync[1],verify_error,verify_done,cfg_done,locked};
 bridge_protocol protocol(
  .clk(clk),.rst_n(rst_n),.rx_data(rx_data),.rx_done(rx_done),.rx_error(rx_error),
  .tx_data(tx_data),.tx_start(tx_start),.tx_busy(tx_busy),
  .req_valid(req_valid),.req_ready(req_ready),.req_write(req_write),.req_addr(req_addr),.req_wdata(req_wdata),
  .rsp_valid(rsp_valid),.rsp_rdata(rsp_rdata),.status_flags(flags),.fail_addr(fail_addr),
  .fail_expected(fail_expected),.fail_actual(fail_actual),
  .overflow_sticky(overflow_sticky),.rx_error_sticky(rx_error_sticky));
 wire vio_trigger,vio_ready,vio_rsp;
 wire [12:0] vio_addr;
 wire [7:0] vio_rdata;
 reg vio_prev,vio_pending,vio_waiting,vio_done;
 reg [12:0] vio_latched_addr;
 reg [7:0] vio_last_data;
 always @(posedge clk) begin
  if(!rst_n) begin
   vio_prev<=0;vio_pending<=0;vio_waiting<=0;vio_done<=0;vio_latched_addr<=0;vio_last_data<=0;
  end else begin
   vio_prev<=vio_trigger;vio_done<=0;
   if(vio_trigger && !vio_prev && !vio_pending && !vio_waiting) begin
    vio_latched_addr<=vio_addr;vio_pending<=1;
   end
   if(vio_pending && vio_ready) begin vio_pending<=0;vio_waiting<=1;end
   if(vio_rsp) begin vio_last_data<=vio_rdata;vio_waiting<=0;vio_done<=1;end
  end
 end
 vio_hmc debug_vio(.clk(clk),.probe_in0(vio_done),.probe_in1(vio_last_data),
  .probe_out0(vio_trigger),.probe_out1(vio_addr));
 wire sdio_out,sdio_oe,sdio_in;
 IOBUF #(.DRIVE(12),.IOSTANDARD("DEFAULT"),.SLEW("SLOW")) sdio_buffer(
  .O(sdio_in),.IO(spi_io),.I(sdio_out),.T(!sdio_oe));
 clock_bridge_core core(
  .clk(clk),.rst_n(rst_n),.req_valid(req_valid),.req_ready(req_ready),.req_write(req_write),
  .req_addr(req_addr),.req_wdata(req_wdata),.rsp_valid(rsp_valid),.rsp_rdata(rsp_rdata),
  .vio_valid(vio_pending),.vio_ready(vio_ready),.vio_addr(vio_latched_addr),.vio_rsp_valid(vio_rsp),.vio_rdata(vio_rdata),
  .cfg_done(cfg_done),.verify_done(verify_done),.verify_error(verify_error),
  .fail_addr(fail_addr),.fail_expected(fail_expected),.fail_actual(fail_actual),
  .busy(busy),.spi_csn(spi_csn),.spi_sclk(spi_clk),.sdio_out(sdio_out),.sdio_oe(sdio_oe),.sdio_in(sdio_in));
 assign led={verify_done && !verify_error,verify_error | vio_pending | vio_waiting,busy,heartbeat[22]};
endmodule
