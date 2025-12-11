"""
视频PDF生成器
将提取的视频信息转换为PDF格式
"""
import logging
from typing import Dict, Any
from datetime import datetime
import io
import base64
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)


class VideoPDFGenerator:
    """视频PDF生成器"""
    
    def __init__(self):
        """初始化PDF生成器"""
        self.page_width, self.page_height = A4
    
    async def generate(
        self,
        video_info: Dict[str, Any],
        options: Dict[str, Any]
    ) -> bytes:
        """
        生成视频转换的PDF文档
        
        Args:
            video_info: 视频信息字典
            options: 转换选项
        
        Returns:
            bytes: PDF文件内容
        """
        logger.info("Generating video PDF")
        
        include_metadata = options.get('include_metadata', True)
        include_frames = options.get('include_frames', True)
        
        # 创建PDF缓冲区
        pdf_buffer = io.BytesIO()
        
        # 创建文档
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
            title="视频内容摘要"
        )
        
        # 获取样式
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # 构建文档内容
        elements = []
        
        # 标题
        elements.append(Paragraph("视频内容摘要", title_style))
        elements.append(Spacer(1, 0.3*inch))
        
        # 元数据
        if include_metadata:
            metadata_content = self._generate_metadata_table(
                video_info['metadata'],
                styles,
                heading_style
            )
            elements.extend(metadata_content)
        
        # 关键帧
        if include_frames and video_info['frames']:
            elements.append(PageBreak())
            elements.append(Paragraph("关键帧内容", heading_style))
            elements.append(Spacer(1, 0.2*inch))
            
            frames_content = self._generate_frames_content(
                video_info['frames'],
                styles,
                heading_style
            )
            elements.extend(frames_content)
        
        # 页脚
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(
            f"<font size=9>文档生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</font>",
            styles['Normal']
        ))
        
        # 构建PDF
        doc.build(elements)
        
        # 获取PDF内容
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.getvalue()
        
        logger.info(f"PDF generated successfully, size: {len(pdf_content)} bytes")
        return pdf_content
    
    def _generate_metadata_table(self, metadata: Dict[str, Any], styles, heading_style) -> list:
        """
        生成元数据表格
        
        Args:
            metadata: 元数据字典
            styles: 样式集
            heading_style: 标题样式
        
        Returns:
            list: 包含表格的元素列表
        """
        elements = []
        elements.append(Paragraph("视频信息", heading_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # 准备表格数据
        data = [["属性", "值"]]
        
        info_items = [
            ("时长", self._format_duration(metadata.get('duration', 0))),
            ("分辨率", metadata.get('resolution', 'N/A')),
            ("帧率", f"{metadata.get('fps', 0):.2f} FPS"),
            ("总帧数", str(metadata.get('total_frames', 0))),
            ("编码格式", metadata.get('codec', 'N/A')),
            ("文件大小", self._format_file_size(metadata.get('file_size', 0))),
            ("提取帧数", str(metadata.get('frames_extracted', 0))),
        ]
        
        for key, value in info_items:
            data.append([key, value])
        
        # 创建表格
        table = Table(data, colWidths=[2.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _generate_frames_content(self, frames: list, styles, heading_style) -> list:
        """
        生成关键帧内容
        
        Args:
            frames: 帧列表
            styles: 样式集
            heading_style: 标题样式
        
        Returns:
            list: 包含帧内容的元素列表
        """
        elements = []
        
        for idx, frame in enumerate(frames):
            # 帧号和时间戳
            frame_title = f"帧 {frame['index'] + 1} - {frame['time_str']}"
            elements.append(Paragraph(f"<b>{frame_title}</b>", styles['Heading3']))
            elements.append(Spacer(1, 0.1*inch))
            
            # 插入图像
            try:
                if frame.get('frame_data'):
                    # 从base64解码图像
                    img_data = base64.b64decode(frame['frame_data'])
                    img_buffer = io.BytesIO(img_data)
                    
                    # 计算图像尺寸（保持宽度，自动调整高度）
                    max_width = 5*inch
                    img = Image(img_buffer, width=max_width, height=max_width * 0.75)
                    elements.append(img)
                    elements.append(Spacer(1, 0.1*inch))
            except Exception as e:
                logger.error(f"Failed to embed frame image: {str(e)}")
            
            # 帧信息
            info_text = (
                f"时间戳: {frame['time_str']} | "
                f"帧号: {frame['frame_number']} | "
                f"分辨率: {frame['width']}x{frame['height']}"
            )
            elements.append(Paragraph(f"<font size=9>{info_text}</font>", styles['Normal']))
            elements.append(Spacer(1, 0.2*inch))
            
            # 每5帧添加一次分页
            if (idx + 1) % 5 == 0 and idx < len(frames) - 1:
                elements.append(PageBreak())
        
        return elements
    
    def _format_duration(self, duration: float) -> str:
        """
        格式化视频时长
        
        Args:
            duration: 秒数
        
        Returns:
            str: 格式化的时长字符串
        """
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
        
        Returns:
            str: 格式化的文件大小
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

