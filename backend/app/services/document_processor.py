#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档处理模块 - 处理用户上传的文档
使用BGE-M3模型进行文档分割和向量化
"""

import os
import re
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime
import uuid

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# BGE-M3模型路径
MODEL_PATH = r"E:\vscode-py\model_cache\models--BAAI--bge-m3"

# 向量数据库存储路径
VECTOR_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "vector_db", "uploaded_docs")
os.makedirs(VECTOR_DB_DIR, exist_ok=True)

class DocumentProcessor:
    """文档处理器 - 负责文档分割、向量化和检索"""

    def __init__(self):
        """初始化文档处理器"""
        logger.info(f"加载BGE-M3模型: {MODEL_PATH}")
        self.model = SentenceTransformer(MODEL_PATH, device='cpu')
        logger.info("BGE-M3模型加载完成")

        # 存储用户文档的FAISS索引
        self.user_indices = {}  # {user_id: faiss_index}
        self.user_documents = {}  # {user_id: {document_id: document_info}}

    def split_document(self, text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        """
        智能文档分割

        参数:
            text: 文档文本
            chunk_size: 每块的最大字符数
            overlap: 块之间的重叠字符数

        返回:
            分割后的文本块列表
        """
        if not text or not text.strip():
            return []

        # 预处理：统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # 按段落分割
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        current_chunk = ""

        for paragraph in paragraphs:
            # 如果当前段落加上当前块超过chunk_size，先保存当前块
            if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # 保留重叠部分
                if overlap > 0:
                    words = current_chunk.split()
                    overlap_text = ' '.join(words[-overlap//2:]) if len(words) > overlap//2 else current_chunk
                    current_chunk = overlap_text + "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())

        logger.info(f"文档分割完成，共 {len(chunks)} 个文本块")
        return chunks

    def create_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        生成文本嵌入向量

        参数:
            texts: 文本列表

        返回:
            嵌入向量数组
        """
        if not texts:
            return np.array([])

        logger.info(f"开始生成嵌入，共 {len(texts)} 个文本")
        embeddings = self.model.encode(
            texts,
            batch_size=4,
            show_progress_bar=True,
            device='cpu',
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        logger.info(f"嵌入生成完成，形状: {embeddings.shape}")
        return embeddings

    def add_document(self, user_id: str, document_id: str, filename: str, 
                     content: str, description: str = "") -> bool:
        """
        添加文档到用户的向量数据库

        参数:
            user_id: 用户ID
            document_id: 文档ID
            filename: 文件名
            content: 文档内容
            description: 文档描述

        返回:
            是否添加成功
        """
        try:
            # 分割文档
            chunks = self.split_document(content)
            if not chunks:
                logger.warning(f"文档分割失败: {filename}")
                return False

            # 生成嵌入向量
            embeddings = self.create_embeddings(chunks)

            # 创建或更新用户的FAISS索引
            if user_id not in self.user_indices:
                dimension = embeddings.shape[1]
                self.user_indices[user_id] = faiss.IndexFlatIP(dimension)
                self.user_documents[user_id] = {}

            # 添加向量到索引
            faiss.normalize_L2(embeddings)
            self.user_indices[user_id].add(embeddings)

            # 存储文档信息
            self.user_documents[user_id][document_id] = {
                "document_id": document_id,
                "filename": filename,
                "description": description,
                "chunks": chunks,
                "chunk_count": len(chunks),
                "upload_time": datetime.now().isoformat(),
                "content_preview": content[:200] + "..." if len(content) > 200 else content
            }

            logger.info(f"文档添加成功: {filename}, 共 {len(chunks)} 个文本块")
            return True

        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return False

    def search_documents(self, user_id: str, query: str, top_k: int = 5, 
                        document_id: Optional[str] = None) -> List[Dict]:
        """
        在用户文档中搜索相关内容

        参数:
            user_id: 用户ID
            query: 查询文本
            top_k: 返回前k个结果
            document_id: 指定文档ID（可选）

        返回:
            搜索结果列表
        """
        if user_id not in self.user_indices:
            logger.warning(f"用户 {user_id} 没有上传文档")
            return []

        if document_id and document_id not in self.user_documents[user_id]:
            logger.warning(f"文档 {document_id} 不存在")
            return []

        try:
            # 生成查询向量
            query_embedding = self.model.encode([query], device='cpu')
            faiss.normalize_L2(query_embedding)

            # 搜索
            distances, indices = self.user_indices[user_id].search(query_embedding, top_k * 2)

            # 过滤结果
            results = []
            seen_chunks = set()

            for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
                if idx == -1:
                    continue

                # 找到对应的文档和块
                for doc_id, doc_info in self.user_documents[user_id].items():
                    # 如果指定了文档ID，只搜索该文档
                    if document_id and doc_id != document_id:
                        continue

                    chunks = doc_info['chunks']
                    if idx < len(chunks):
                        chunk_key = f"{doc_id}_{idx}"
                        if chunk_key not in seen_chunks:
                            seen_chunks.add(chunk_key)
                            results.append({
                                'text': chunks[idx],
                                'filename': doc_info['filename'],
                                'document_id': doc_id,
                                'description': doc_info.get('description', ''),
                                'score': float(dist),
                                'chunk_index': idx
                            })

                            if len(results) >= top_k:
                                break

                if len(results) >= top_k:
                    break

            return results

        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return []

    def get_user_documents(self, user_id: str) -> List[Dict]:
        """
        获取用户的所有文档信息

        参数:
            user_id: 用户ID

        返回:
            文档信息列表
        """
        if user_id not in self.user_documents:
            return []

        return list(self.user_documents[user_id].values())

    def delete_document(self, user_id: str, document_id: str) -> bool:
        """
        删除用户的文档

        参数:
            user_id: 用户ID
            document_id: 文档ID

        返回:
            是否删除成功
        """
        if user_id not in self.user_documents:
            return False

        if document_id not in self.user_documents[user_id]:
            return False

        try:
            # 删除文档信息
            del self.user_documents[user_id][document_id]

            # 如果用户没有文档了，删除索引
            if not self.user_documents[user_id]:
                del self.user_indices[user_id]
                del self.user_documents[user_id]
            else:
                # 重建索引
                self._rebuild_index(user_id)

            logger.info(f"文档删除成功: {document_id}")
            return True

        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return False

    def _rebuild_index(self, user_id: str):
        """重建用户的FAISS索引"""
        if user_id not in self.user_documents:
            return

        # 创建新索引
        dimension = self.model.get_sentence_embedding_dimension()
        new_index = faiss.IndexFlatIP(dimension)

        # 重新添加所有文档的向量
        for doc_id, doc_info in self.user_documents[user_id].items():
            chunks = doc_info['chunks']
            embeddings = self.create_embeddings(chunks)
            faiss.normalize_L2(embeddings)
            new_index.add(embeddings)

        # 替换旧索引
        self.user_indices[user_id] = new_index

        logger.info(f"用户 {user_id} 的索引重建完成")

# 全局文档处理器实例
document_processor = DocumentProcessor()
