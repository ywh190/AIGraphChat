#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中医药知识图谱系统 - FAISS RAG服务模块
使用FAISS向量数据库进行语义检索
"""

import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
import pathlib


def generate_expanded_queries_ai_only(original_query: str) -> List[str]:
    """
    使用AI模型自主生成扩展查询词（不使用任何固定模板）
    让AI完全根据中医药专业知识自由发挥
    """
    try:
        # 动态导入AI服务，避免循环导入
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from app.services.ai_service import call_ai_model
        
        # 首先识别查询类型
        type_prompt = f"""请判断以下查询是关于"方剂"还是"中成药"的查询。
查询："{original_query}"

如果查询涉及"颗粒"、"胶囊"、"片"、"口服液"等现代剂型，或者明确是中成药名称，请回答"中成药"。
如果查询涉及"汤"、"散"、"丸"、"膏"等传统剂型，或者明确是传统方剂名称，请回答"方剂"。

只回答"方剂"或"中成药"，不要返回其他内容。"""

        query_type = call_ai_model(type_prompt, max_tokens=10).strip()

        # 让AI生成相关查询，并确保类型一致
        prompt = f"""作为中医药专家，请基于"{original_query}"这个查询，生成3-5个相关的专业查询。
要求：
- 查询类型必须是：{query_type}
- 完全基于你的中医药专业知识自由发挥
- 覆盖功效、组成、适应症等不同角度
- 每个查询应该是完整的问句或短语
- 不要重复原始查询
- **绝对禁止**：如果查询类型是"方剂"，不要生成包含"颗粒"、"胶囊"、"片"等中成药特征的查询
- **绝对禁止**：如果查询类型是"中成药"，不要生成包含"汤"、"散"等传统方剂特征的查询

请直接返回查询列表，每行一个："""
        
        ai_response = call_ai_model(prompt, max_tokens=200)
        
        if ai_response:
            expanded_queries = []
            lines = ai_response.strip().split('\n')
            for line in lines:
                line = line.strip()
                # 清理可能的序号
                import re
                line = re.sub(r'^\d+\.\s*', '', line)
                line = re.sub(r'^[-*]\s*', '', line)
                if line and len(line) > 2:
                    expanded_queries.append(line)
            
            return expanded_queries[:5]  # 最多5个扩展查询
        
        return []
        
    except Exception as e:
        logger.warning(f"AI查询扩展失败: {e}")
        return []


def calculate_query_similarity(query1: str, query2: str, model) -> float:
    """计算两个查询之间的余弦相似度"""
    try:
        embeddings = model.encode([query1, query2])
        faiss.normalize_L2(embeddings)
        similarity = np.dot(embeddings[0], embeddings[1])
        return float(similarity)
    except Exception as e:
        logger.warning(f"相似度计算失败: {e}")
        return 0.0


def smart_query_expansion(original_query: str, model, similarity_threshold: float = 0.8) -> str:
    """
    智能查询扩展：
    1. 让AI自主生成扩展查询（无模板约束）
    2. 验证每个扩展查询与原查询的相似度
    3. 组合原始查询 + 通过验证的扩展查询
    """
    try:
        # 始终以原始查询开始
        valid_queries = [original_query]
        
        # 获取AI生成的扩展查询
        ai_expanded_queries = generate_expanded_queries_ai_only(original_query)
        
        # 验证每个扩展查询的相似度
        for expanded_query in ai_expanded_queries:
            similarity = calculate_query_similarity(original_query, expanded_query, model)
            if similarity >= similarity_threshold:
                valid_queries.append(expanded_query)
                logger.info(f"AI扩展查询通过验证: '{expanded_query}' (相似度: {similarity:.3f})")
            else:
                logger.debug(f"AI扩展查询被过滤: '{expanded_query}' (相似度: {similarity:.3f} < {similarity_threshold})")
        
        # 组合所有有效查询
        combined_query = " ".join(valid_queries)
        return combined_query
        
    except Exception as e:
        logger.warning(f"智能查询扩展失败，回退到原始查询: {e}")
        return original_query

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 延迟导入以避免循环依赖
def get_global_model():
    """获取全局共享的嵌入模型"""
    from app.services.ai_service import get_embedding_model
    return get_embedding_model()

class FAISSRAGService:
    """FAISS向量检索服务"""
    
    def __init__(self, model_path: str, index_path: str, metadata_path: str):
        """
        初始化FAISS RAG服务
        
        Args:
            model_path: BGE-M3模型路径
            index_path: FAISS索引文件路径
            metadata_path: 元数据文件路径
        """
        self.model_path = model_path
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.model = None
        self.index = None
        self.texts = []
        self.metadatas = []
        
        # 只加载索引，不加载模型（使用全局模型）
        self._load_index()
    
    def _load_model(self):
        """加载嵌入模型"""
        try:
            logger.info(f"加载BGE-M3模型: {self.model_path}")
            # 强制使用CPU模式以避免GPU内存不足问题
            import torch
            device = "cpu"  # 强制使用CPU
            self.model = SentenceTransformer(self.model_path, device=device)
            logger.info(f"BGE-M3模型加载成功，使用设备: {device}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def _load_index(self):
        """加载FAISS索引和元数据"""
        try:
            # 使用相对路径构建完整路径
            import sys
            import pathlib
            
            # 获取当前文件所在目录
            current_file = pathlib.Path(__file__).resolve()
            backend_dir = current_file.parent.parent.parent  # backend/app/services -> backend
            index_path = backend_dir / "data" / "vector_db" / "knowledge_base.index"
            metadata_path = backend_dir / "data" / "vector_db" / "knowledge_base_metadata.json"
            
            # 路径规范化和编码处理
            self.index_path = os.path.normpath(str(index_path))
            self.metadata_path = os.path.normpath(str(metadata_path))
            
            # 尝试使用sys.getfilesystemencoding()处理路径
            if hasattr(os, 'fsencode'):
                index_bytes = os.fsencode(self.index_path)
                self.index_path = os.fsdecode(index_bytes)
                metadata_bytes = os.fsencode(self.metadata_path)
                self.metadata_path = os.fsdecode(metadata_bytes)
            
            logger.info(f"FAISS索引路径: {self.index_path}")
            logger.info(f"元数据路径: {self.metadata_path}")
            
            if not os.path.exists(self.index_path):
                logger.warning(f"FAISS索引文件不存在: {self.index_path}")
                return
            
            if not os.path.exists(self.metadata_path):
                logger.warning(f"元数据文件不存在: {self.metadata_path}")
                return
            
            # 加载FAISS索引
            logger.info(f"加载FAISS索引: {self.index_path}")
            self.index = faiss.read_index(self.index_path)
            
            # 加载元数据
            logger.info(f"加载元数据: {self.metadata_path}")
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.texts = data['texts']
                self.metadatas = data['metadatas']
            
            logger.info(f"FAISS索引加载成功，包含 {len(self.texts)} 个文档")
            
        except Exception as e:
            logger.error(f"索引加载失败: {e}")
            raise
    
    def search(self, query: str, k: int = 5, balanced: bool = False, use_smart_expansion: bool = True) -> List[Dict]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            balanced: 是否平衡返回不同类型的结果
            use_smart_expansion: 是否使用智能查询扩展
        """
        if self.index is None or len(self.texts) == 0:
            logger.warning("FAISS索引未加载或为空")
            return []
        
        try:
            # 智能查询扩展
            actual_query = query
            if use_smart_expansion:
                model = get_global_model()
                actual_query = smart_query_expansion(query, model, similarity_threshold=0.8)
                if actual_query != query:
                    logger.info(f"使用智能扩展查询: '{query}' -> '{actual_query[:100]}...'")
            
            # 生成查询嵌入
            model = get_global_model()
            query_embedding = model.encode([actual_query])
            faiss.normalize_L2(query_embedding)
            
            if balanced:
                # 平衡检索：先获取更多结果，然后按类型平衡选择
                total_k = min(k * 3, len(self.texts))  # 获取3倍结果用于筛选
                scores, indices = self.index.search(query_embedding, total_k)
                
                # 按类型分组
                results_by_type = {"herb": [], "prescription": [], "medic": []}
                for i, idx in enumerate(indices[0]):
                    if idx < len(self.texts):
                        result = {
                            "text": self.texts[idx],
                            "metadata": self.metadatas[idx],
                            "score": float(scores[0][i])
                        }
                        doc_type = result["metadata"].get("type", "unknown")
                        if doc_type in results_by_type:
                            results_by_type[doc_type].append(result)
                
                # 平衡选择结果
                balanced_results = []
                remaining_slots = k
                
                # 优先保证每种类型至少有1个结果（如果存在且得分>0.2）
                for doc_type in ["prescription", "herb", "medic"]:
                    valid_results = [r for r in results_by_type[doc_type] if r["score"] > 0.2]
                    if valid_results and remaining_slots > 0:
                        balanced_results.append(valid_results[0])
                        remaining_slots -= 1
                
                # 填充剩余位置，按得分排序
                all_remaining = []
                for doc_type in ["prescription", "herb", "medic"]:
                    valid_results = [r for r in results_by_type[doc_type] if r["score"] > 0.2]
                    all_remaining.extend(valid_results[1:])
                
                all_remaining.sort(key=lambda x: x["score"], reverse=True)
                balanced_results.extend(all_remaining[:remaining_slots])
                
                return balanced_results[:k]
            else:
                # 原始检索方式
                scores, indices = self.index.search(query_embedding, k)
                results = []
                for i, idx in enumerate(indices[0]):
                    if idx < len(self.texts):  # 确保索引有效
                        results.append({
                            "text": self.texts[idx],
                            "metadata": self.metadatas[idx],
                            "score": float(scores[0][i])  # 转换为Python float
                        })
                return results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return self.index is not None and len(self.texts) > 0

# 全局FAISS RAG服务实例
FAISS_RAG_SERVICE: Optional[FAISSRAGService] = None

def init_faiss_rag_service() -> Optional[FAISSRAGService]:
    """初始化FAISS RAG服务"""
    global FAISS_RAG_SERVICE
    
    if FAISS_RAG_SERVICE is not None:
        return FAISS_RAG_SERVICE
    
    try:
        # 模型路径配置
        model_cache_dir = os.getenv("MODEL_CACHE_DIR", "E:\\vscode-py\\model_cache")
        bge_m3_path = os.path.join(model_cache_dir, "models--BAAI--bge-m3")
        
        # 索引和元数据路径
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        index_path = os.path.join(backend_dir, "data", "vector_db", "knowledge_base.index")
        metadata_path = os.path.join(backend_dir, "data", "vector_db", "knowledge_base_metadata.json")
        
        FAISS_RAG_SERVICE = FAISSRAGService(bge_m3_path, index_path, metadata_path)
        logger.info("FAISS RAG服务初始化成功")
        return FAISS_RAG_SERVICE
        
    except Exception as e:
        logger.error(f"FAISS RAG服务初始化失败: {e}")
        return None

def search_knowledge_base(query: str, k: int = 5) -> List[Dict]:
    """
    搜索知识库（原始方式，使用智能查询扩展）
    """
    global FAISS_RAG_SERVICE
    
    if FAISS_RAG_SERVICE is None:
        FAISS_RAG_SERVICE = init_faiss_rag_service()
    
    if FAISS_RAG_SERVICE is None or not FAISS_RAG_SERVICE.is_ready():
        logger.warning("FAISS RAG服务不可用，返回空结果")
        return []
    
    return FAISS_RAG_SERVICE.search(query, k, balanced=False, use_smart_expansion=True)

def search_knowledge_base_balanced(query: str, k: int = 5) -> List[Dict]:
    """
    搜索知识库（平衡方式）- 确保返回多种类型的结果，使用智能查询扩展
    """
    global FAISS_RAG_SERVICE
    
    if FAISS_RAG_SERVICE is None:
        FAISS_RAG_SERVICE = init_faiss_rag_service()
    
    if FAISS_RAG_SERVICE is None or not FAISS_RAG_SERVICE.is_ready():
        logger.warning("FAISS RAG服务不可用，返回空结果")
        return []
    
    return FAISS_RAG_SERVICE.search(query, k, balanced=True, use_smart_expansion=True)

def search_knowledge_base_with_expanded_query(expanded_query: str, k: int = 5) -> List[Dict]:
    """
    使用已扩展的查询搜索知识库（平衡方式）
    此函数假设传入的查询已经过AI扩展处理，直接进行检索而不进行二次扩展
    """
    global FAISS_RAG_SERVICE
    
    if FAISS_RAG_SERVICE is None:
        FAISS_RAG_SERVICE = init_faiss_rag_service()
    
    if FAISS_RAG_SERVICE is None or not FAISS_RAG_SERVICE.is_ready():
        logger.warning("FAISS RAG服务不可用，返回空结果")
        return []
    
    # 直接使用传入的已扩展查询，禁用内部的智能扩展
    return FAISS_RAG_SERVICE.search(expanded_query, k, balanced=True, use_smart_expansion=False)

# 测试函数
if __name__ == "__main__":
    # 初始化服务
    service = init_faiss_rag_service()