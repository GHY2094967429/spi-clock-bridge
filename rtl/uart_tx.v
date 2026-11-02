`timescale 1ns/1ps
module uart_tx #(
    parameter CLK_FREQ  = 5_000_000,    
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] tx_data,
    input  wire       tx_start,
    output reg        tx_busy,
    output reg        tx_pin
);
    localparam CLK_COUNT = CLK_FREQ / BAUD_RATE;

    reg [15:0] clk_cnt;
    reg [3:0]  bit_cnt;
    reg [7:0]  tx_reg;
    
    localparam IDLE  = 2'd0;
    localparam START = 2'd1;
    localparam DATA  = 2'd2;
    localparam STOP  = 2'd3;

    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= IDLE;
            tx_pin  <= 1'b1; // UART Idle is High
            tx_busy <= 1'b0;
            clk_cnt <= 16'd0;
            bit_cnt <= 4'd0;
            tx_reg  <= 8'd0;
        end else begin
            case (state)
                IDLE: begin
                    tx_pin <= 1'b1;
                    if (tx_start) begin
                        state   <= START;
                        tx_busy <= 1'b1;
                        tx_reg  <= tx_data;
                        clk_cnt <= 16'd0;
                    end else begin
                        tx_busy <= 1'b0;
                    end
                end

                START: begin
                    tx_pin <= 1'b0; // Start Bit
                    if (clk_cnt == CLK_COUNT - 1) begin
                        clk_cnt <= 16'd0;
                        state   <= DATA;
                        bit_cnt <= 4'd0;
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                DATA: begin
                    tx_pin <= tx_reg[bit_cnt]; // Data Bit
                    if (clk_cnt == CLK_COUNT - 1) begin
                        clk_cnt <= 16'd0;
                        if (bit_cnt == 4'd7) begin
                            state <= STOP;
                        end else begin
                            bit_cnt <= bit_cnt + 1'b1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                STOP: begin
                    tx_pin <= 1'b1; // Stop Bit
                    if (clk_cnt == CLK_COUNT - 1) begin
                        clk_cnt <= 16'd0;
                        state   <= IDLE;
                        tx_busy <= 1'b0; // Done
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end
                
                default: state <= IDLE;
            endcase
        end
    end
endmodule