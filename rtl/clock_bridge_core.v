`timescale 1ns/1ps
// Reusable register bridge: all interface signals are synchronous to clk.
// Hold req_valid and payload until req_ready. Each acceptance gives one rsp_valid pulse.
// Initialization owns SPI until verification ends; UART/user wins over VIO afterwards.
module clock_bridge_core #(parameter SPI_HALF_PERIOD=2, parameter SETTLE_CYCLES=5000)(
 input wire clk, input wire rst_n,
 input wire req_valid, output wire req_ready, input wire req_write,
 input wire [12:0] req_addr, input wire [7:0] req_wdata,
 output wire rsp_valid, output wire [7:0] rsp_rdata,
 input wire vio_valid, output wire vio_ready, input wire [12:0] vio_addr,
 output wire vio_rsp_valid, output wire [7:0] vio_rdata,
 output wire cfg_done, output wire verify_done, output wire verify_error,
 output wire [12:0] fail_addr, output wire [7:0] fail_expected, output wire [7:0] fail_actual,
 output wire busy, output wire spi_csn, output wire spi_sclk,
 output wire sdio_out, output wire sdio_oe, input wire sdio_in
);
 wire c_valid,c_ready,c_write,c_rsp;
 wire [12:0] c_addr;
 wire [7:0] c_data,m_rdata;
 wire m_ready,m_rsp;
 reg [1:0] owner;
 wire cfg_selected=!verify_done;
 wire user_selected=verify_done && req_valid;
 wire vio_selected=verify_done && !req_valid;
 wire idle=owner==0;
 wire m_valid=idle && (cfg_selected ? c_valid : (req_valid || vio_valid));
 wire m_write=cfg_selected ? c_write : (user_selected ? req_write : 1'b0);
 wire [12:0] m_addr=cfg_selected ? c_addr : (user_selected ? req_addr : vio_addr);
 wire [7:0] m_data=cfg_selected ? c_data : req_wdata;
 assign c_ready=idle && m_ready && cfg_selected;
 assign req_ready=idle && m_ready && user_selected;
 assign vio_ready=idle && m_ready && vio_selected;
 assign c_rsp=m_rsp && owner==1;
 assign rsp_valid=m_rsp && owner==2;
 assign vio_rsp_valid=m_rsp && owner==3;
 assign rsp_rdata=m_rdata;
 assign vio_rdata=m_rdata;
 always @(posedge clk) begin
  if(!rst_n) owner<=0;
  else if(m_rsp) owner<=0;
  else if(m_valid && m_ready) owner<=cfg_selected ? 1 : (user_selected ? 2 : 3);
 end
 hmc7044_init #(.SETTLE_CYCLES(SETTLE_CYCLES)) init_seq(
  .clk(clk),.rst_n(rst_n),.req_valid(c_valid),.req_ready(c_ready),.req_write(c_write),
  .req_addr(c_addr),.req_wdata(c_data),.rsp_valid(c_rsp),.rsp_rdata(m_rdata),
  .cfg_done(cfg_done),.verify_done(verify_done),.verify_error(verify_error),
  .fail_addr(fail_addr),.fail_expected(fail_expected),.fail_actual(fail_actual));
 spi_reg_master #(.HALF_PERIOD(SPI_HALF_PERIOD)) spi(
  .clk(clk),.rst_n(rst_n),.req_valid(m_valid),.req_ready(m_ready),.req_write(m_write),
  .req_addr(m_addr),.req_wdata(m_data),.rsp_valid(m_rsp),.rsp_rdata(m_rdata),.busy(busy),
  .spi_csn(spi_csn),.spi_sclk(spi_sclk),.sdio_out(sdio_out),.sdio_oe(sdio_oe),.sdio_in(sdio_in));
endmodule
