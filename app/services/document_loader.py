"""
app/services/document_loader.py
=================================
文档加载服务。

负责从各种格式的文件中提取纯文本内容。
支持的格式: PDF, DOCX, TXT

技术选型:
- PDF: PyMuPDF (fitz) 或 pdfplumber
- DOCX: python-docx
- TXT: 直接读取
"""

from typing import List


def load_pdf(file_path: str) -> str:
    """
    从 PDF 文件提取纯文本。

    参数:
        file_path: PDF 文件路径
    返回:
        str: 提取的纯文本内容
    """
    # TODO: 实现 PDF 文本提取
    # 使用 PyMuPDF: pip install PyMuPDF
    # import fitz
    # doc = fitz.open(file_path)
    # text = ""
    # for page in doc:
    #     text += page.get_text()
    pass


def load_docx(file_path: str) -> str:
    """
    从 DOCX 文件提取纯文本。

    参数:
        file_path: DOCX 文件路径
    返回:
        str: 提取的纯文本内容
    """
    # TODO: 实现 DOCX 文本提取
    pass


def load_txt(file_path: str) -> str:
    """
    从 TXT 文件读取纯文本。

    参数:
        file_path: TXT 文件路径
    返回:
        str: 文件内容
    """
    # TODO: 实现 TXT 读取
    pass


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    将长文本切分为固定大小的 chunks。

    切分是为了:
    1. 适配 LLM 的上下文窗口限制
    2. 提高向量检索的精度

    参数:
        text: 要切分的原始文本
        chunk_size: 每个 chunk 的目标字符数 (默认 500)
        overlap: 相邻 chunk 之间的重叠字符数 (默认 50)
                 重叠可以防止重要信息正好落在 chunk 边界处被截断
    返回:
        List[str]: 切分后的文本块列表
    """
    # TODO: 实现文本切分
    # 1. 按 chunk_size 滑动窗口切分
    # 2. 每个窗口 advance = chunk_size - overlap
    # 3. 尽量在句子边界处切分 (更自然)
    pass
