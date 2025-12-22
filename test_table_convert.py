# -*- coding: utf-8 -*-
"""
测试 HTML 表格转 Word
"""
import sys
sys.path.insert(0, r'D:\Data Processing Module\data_to_md-main')

from app.core.converters.image.word_formatter import WordFormatter

# 读取 HTML 文件
with open(r'D:\Data Processing Module\test.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# 分析表格结构
from bs4 import BeautifulSoup
soup = BeautifulSoup(html_content, 'html.parser')
table = soup.find('table')
rows = table.find_all('tr')

print(f"总行数: {len(rows)}")
print("\n每行的单元格分析:")
print("-" * 80)

max_cols = 0
for i, row in enumerate(rows):
    cells = row.find_all(['td', 'th'])
    total_cols = 0
    cell_details = []
    for cell in cells:
        colspan = int(cell.get('colspan', 1))
        total_cols += colspan
        text = cell.get_text()[:20].replace('\n', ' ')
        cell_details.append(f"'{text}'(colspan={colspan})")
    
    max_cols = max(max_cols, total_cols)
    print(f"Row {i:2d}: 单元格数={len(cells):2d}, 实际列数={total_cols:2d}")
    if i < 5:  # 只显示前5行的详细信息
        print(f"        {', '.join(cell_details[:5])}...")
    print()

print(f"\n最大列数: {max_cols}")

# 测试转换
print("\n开始转换到 Word...")
formatter = WordFormatter()
output_path = r'D:\Data Processing Module\test_output.docx'
formatter.markdown_to_docx(html_content, output_path)
print(f"转换完成: {output_path}")
