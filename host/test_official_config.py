"""Importer validation: syntax is data; never execute an exported Python file."""
import tempfile
import unittest
from pathlib import Path
from official_config import parse_adi_python, load_configuration


class OfficialConfigTests(unittest.TestCase):
    def test_write_order_duplicates_comments_and_number_bases(self):
        steps = parse_adi_python('# original field\ndut.write(0x8, 0xA5)\ndut.write(8, 90)\ndut.write(10, 255)\n')
        self.assertEqual([(s.address, s.data) for s in steps], [(8, 165), (8, 90), (10, 255)])
        self.assertEqual(steps[0].comment, 'original field')
        self.assertEqual([s.line for s in steps], [2, 3, 4])

    def test_delay_stays_between_writes_and_rounds_up(self):
        steps = parse_adi_python('import time\ndut.write(8,1)\ntime.sleep(0.0001)\ndut.write(8,2)')
        self.assertEqual([s.kind for s in steps], ['write','delay','write'])
        self.assertEqual(steps[1].delay_ms, 1)

    def test_unknown_code_is_rejected_even_after_valid_writes(self):
        for code in ['import os', 'dut.read(8)', 'open("test", "w")', 'for i in range(4):\n dut.write(i,0)',
                     'dut.write(8, int("2"))', 'dut.write(8, 1+1)', 'dut.write(address=8,data=2)',
                     'dut.write(True,1)', 'dut.write(8,False)', 'exec("dut.write(8,1)")']:
            with self.subTest(code=code), self.assertRaises(ValueError):
                parse_adi_python('dut.write(8,1)\n'+code)

    def test_out_of_range_and_syntax_errors(self):
        for code in ['dut.write(0x2000,0)', 'dut.write(8,0x100)', 'dut.write(-1,0)',
                     'dut.write(8,1', 'time.sleep(61)\ndut.write(8,1)',
                     'time.sleep('+('9'*400)+')\ndut.write(8,1)',
                     'dut.write(8,1)\n'+'time.sleep(60)\n'*6]:
            with self.subTest(code=code), self.assertRaises(ValueError):parse_adi_python(code)

    def test_file_metadata_and_utf16(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'export.py';p.write_text('# 配置\ndut.write(8,1)\ndut.write(8,2)\n',encoding='utf-16')
            result=load_configuration(p)
            self.assertEqual((result.write_count,result.duplicate_count),(2,1))
            self.assertEqual(result.filename,'export.py')
            self.assertEqual(len(result.sha256),64)

    def test_csv_roundtrip_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'result.csv';p.write_text('address,data,actual,result,source_line,comment\n0010,5A,5A,OK,2,field\n0010,A5,A5,OK,3,\n',encoding='utf-8-sig')
            cfg=load_configuration(p)
            self.assertEqual([(s.address,s.data) for s in cfg.steps],[(16,90),(16,165)])

    def test_no_writes_or_excessive_input_rejected(self):
        for text in ['# comment only', 'time.sleep(0)', 'dut.write(8,0)\n'*4097]:
            with self.assertRaises(ValueError):parse_adi_python(text)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'large.py';p.write_bytes(b'#'*(1024*1024+1))
            with self.assertRaisesRegex(ValueError,'MiB'):load_configuration(p)


if __name__=='__main__':unittest.main()
