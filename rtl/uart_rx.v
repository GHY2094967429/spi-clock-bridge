`timescale 1ns/1ps
module uart_rx #(
    parameter CLK_FREQ  = 5_000_000,   
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_pin,
    output reg  [7:0] rx_data,
    output reg        rx_error,
    output reg        rx_done
);
    // 波特率计数计算
    localparam CLK_COUNT = CLK_FREQ / BAUD_RATE;
    localparam MID_COUNT = CLK_COUNT / 2;

    reg [1:0] rx_sync;
    reg [15:0] clk_cnt;
    reg [3:0]  bit_cnt;

    // 异步信号同步化 (消除亚稳态)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rx_sync <= 2'b11;
        else        rx_sync <= {rx_sync[0], rx_pin};
    end
    wire rx_bit = rx_sync[1];

    // 状态机
    localparam IDLE  = 2'd0;
    localparam START = 2'd1;
    localparam DATA  = 2'd2;
    localparam STOP  = 2'd3;

    reg [1:0] state;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= IDLE;
            clk_cnt  <= 16'd0;
            bit_cnt  <= 4'd0;
            rx_done  <= 1'b0;
            rx_error <= 1'b0;
            rx_data  <= 8'd0;
        end else begin
            rx_done <= 1'b0; rx_error <= 1'b0; // Default
            
            case (state)
                IDLE: begin
                    if (rx_bit == 1'b0) begin // 检测到起始位下降沿
                        state   <= START;
                        clk_cnt <= 16'd0;
                    end
                end

                START: begin
                    if (clk_cnt == MID_COUNT - 1) begin // 在起始位中间采样
                        if (rx_bit == 1'b0) begin
                            state   <= DATA;
                            clk_cnt <= 16'd0;
                            bit_cnt <= 4'd0;
                        end else begin
                            state <= IDLE; // 误触发
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end

                DATA: begin
                    if (clk_cnt == CLK_COUNT - 1) begin
                        clk_cnt <= 16'd0;
                        rx_data[bit_cnt] <= rx_bit; // 移位接收
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
                    if (clk_cnt == CLK_COUNT - 1) begin
                        state   <= IDLE;
                        rx_done <= rx_bit; rx_error <= !rx_bit; // Check stop bit
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end
                
                default: state <= IDLE;
            endcase
        end
    end
endmodule
