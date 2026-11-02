`timescale 1ns/1ps
// One 24-bit, MSB-first HMC7044 transaction. SPI mode 0.
module spi_reg_master #(parameter HALF_PERIOD = 2)(
 input wire clk, input wire rst_n,
 input wire req_valid, output wire req_ready,
 input wire req_write, input wire [12:0] req_addr, input wire [7:0] req_wdata,
 output reg rsp_valid, output reg [7:0] rsp_rdata,
 output wire busy, output reg spi_csn, output reg spi_sclk,
 output reg sdio_out, output reg sdio_oe, input wire sdio_in
);
 localparam CW = (HALF_PERIOD < 2) ? 1 : $clog2(HALF_PERIOD);
 localparam IDLE=0, TRANSFER=1, HOLD=2;
 reg [1:0] state;
 reg [CW-1:0] divider;
 reg [23:0] shift;
 reg [4:0] bit_index;
 reg reading;
 reg [7:0] rx_shift;
 assign req_ready = state == IDLE;
 assign busy = state != IDLE;
 always @(posedge clk) begin
  if (!rst_n) begin
   state<=IDLE; divider<=0; shift<=0; bit_index<=0; reading<=0;
   rx_shift<=0; rsp_rdata<=0; rsp_valid<=0;
   spi_csn<=1; spi_sclk<=0; sdio_out<=0; sdio_oe<=0;
  end else begin
   rsp_valid<=0;
   case(state)
    IDLE: if(req_valid) begin
     shift<={!req_write,2'b00,req_addr,req_wdata};
     sdio_out<=!req_write; sdio_oe<=1;
     spi_csn<=0; spi_sclk<=0; bit_index<=23;
     divider<=0; rx_shift<=0; reading<=!req_write; state<=TRANSFER;
    end
    TRANSFER: if(divider == HALF_PERIOD-1) begin
     divider<=0;
     if(!spi_sclk) begin
      spi_sclk<=1;
      if(reading && bit_index<8) rx_shift<={rx_shift[6:0],sdio_in};
     end else begin
      spi_sclk<=0;
      // Keep A0 driven through its sampling edge; turn around on the next falling edge.
      if(reading && bit_index==8) sdio_oe<=0;
      if(bit_index==0) begin
       spi_csn<=1; sdio_oe<=0; state<=HOLD;
      end else begin
       bit_index<=bit_index-1'b1;
       shift<={shift[22:0],1'b0}; sdio_out<=shift[22];
      end
     end
    end else divider<=divider+1'b1;
    HOLD: if(divider == HALF_PERIOD-1) begin
     divider<=0; rsp_rdata<=rx_shift; rsp_valid<=1; state<=IDLE;
    end else divider<=divider+1'b1;
    default: state<=IDLE;
   endcase
  end
 end
endmodule
