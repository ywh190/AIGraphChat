#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI服务模块 - 提供智能问答、文档分析等功能
"""

import os
import sys
import re
import json
import requests
import asyncio
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import uuid
from dotenv import load_dotenv

# 添加项目根目录到Python路径（如果需要）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 配置日志
logger = logging.getLogger(__name__)

# 全局模型缓存
_model_cache = None
_model_lock = None

# 查询扩展缓存
from functools import lru_cache

def preprocess_query(query: str) -> str:
    """
    预处理用户查询，标准化输入以提高AI扩展和相似度计算的准确性
    
    处理内容包括：
    - 去除首尾空白字符
    - 标准化空格（将多个空格、制表符、换行符替换为单个空格）
    - 移除常见的标点符号干扰（问号、感叹号、句号等）
    - 处理全角/半角字符转换
    - 移除多余的括号和引号
    """
    if not query or not isinstance(query, str):
        return ""
    
    # 1. 去除首尾空白
    processed = query.strip()
    
    # 2. 标准化空格（处理中文全角空格、英文空格、制表符、换行符等）
    processed = re.sub(r'[\s\u3000]+', ' ', processed)
    
    # 3. 移除常见的标点符号干扰（保留中文标点如顿号、逗号等可能有意义的符号）
    # 移除问号、感叹号、句号、分号等结尾标点
    processed = re.sub(r'[？?！!。.;；]+$', '', processed)
    # 移除开头的标点符号
    processed = re.sub(r'^[？?！!。.;；]+', '', processed)
    
    # 4. 处理全角/半角字符转换（主要针对数字和英文字母）
    def full_to_half(text):
        result = []
        for char in text:
            code = ord(char)
            if code == 12288:  # 全角空格
                result.append(chr(32))
            elif 65281 <= code <= 65374:  # 全角字符范围
                result.append(chr(code - 65248))
            else:
                result.append(char)
        return ''.join(result)
    
    processed = full_to_half(processed)
    
    # 5. 移除多余的括号和引号（只在成对出现且包裹整个查询时移除）
    if len(processed) >= 2:
        if (processed.startswith('"') and processed.endswith('"')) or \
           (processed.startswith("'") and processed.endswith("'")) or \
           (processed.startswith('「') and processed.endswith('」')) or \
           (processed.startswith('『') and processed.endswith('』')):
            processed = processed[1:-1].strip()
    
    # 6. 再次去除首尾空白
    processed = processed.strip()
    
    # 7. 如果处理后为空，返回原查询（避免完全删除有效内容）
    if not processed:
        return query.strip()
    
    return processed

def identify_query_type(query: str) -> str:
    """
    识别查询类型：方剂、中成药或药材

    Args:
        query: 用户查询文本

    Returns:
        "prescription"（方剂）、"medic"（中成药）或"herb"（药材）
    """
    if not query:
        return "unknown"

    # 中成药特征关键词
    medic_keywords = ["颗粒", "胶囊", "片", "口服液", "丸", "滴丸", "合剂", "糖浆", "酊剂", "气雾剂", "喷雾剂", "贴膏", "软膏"]

    # 方剂特征关键词
    prescription_keywords = ["汤", "散", "丸", "膏", "丹"]

    # 检查是否包含中成药特征
    for keyword in medic_keywords:
        if keyword in query:
            return "medic"

    # 检查是否包含方剂特征（排除中成药的情况）
    for keyword in prescription_keywords:
        if keyword in query:
            # 如果同时包含"颗粒"等中成药特征，优先判断为中成药
            if any(mk in query for mk in medic_keywords):
                return "medic"
            return "prescription"

    # 如果没有明确特征，使用AI判断
    try:
        type_prompt = f"""请判断以下查询是关于"方剂"还是"中成药"的查询。
查询："{query}"

如果查询涉及"颗粒"、"胶囊"、"片"、"口服液"等现代剂型，或者明确是中成药名称，请回答"中成药"。
如果查询涉及"汤"、"散"、"丸"、"膏"等传统剂型，或者明确是传统方剂名称，请回答"方剂"。

只回答"方剂"或"中成药"，不要返回其他内容。"""

        result = call_ai_model(type_prompt, max_tokens=10).strip()
        if "中成药" in result:
            return "medic"
        elif "方剂" in result:
            return "prescription"
    except Exception as e:
        logger.warning(f"AI类型识别失败: {e}")

    return "unknown"

@lru_cache(maxsize=1000)
def get_expanded_queries_cached(question: str) -> List[str]:
    """缓存的查询扩展"""
    try:
        # 预处理查询
        processed_question = preprocess_query(question)
        if not processed_question:
            return []
        
        model = get_embedding_model()
        
        # 获取AI生成的扩展查询列表
        ai_expanded_queries = generate_expanded_queries_ai_only(processed_question)
        expanded_queries = []
        
        # 对每个扩展查询与原问题做相似度计算
        for expanded_query in ai_expanded_queries:
            similarity = calculate_query_similarity(processed_question, expanded_query, model)
            if similarity >= 0.8:
                expanded_queries.append(expanded_query)
                logger.info(f"AI扩展查询通过验证: '{expanded_query}' (相似度: {similarity:.3f})")
            else:
                logger.debug(f"AI扩展查询被过滤: '{expanded_query}' (相似度: {similarity:.3f} < 0.8)")
        
        return expanded_queries
    except Exception as e:
        logger.warning(f"AI查询扩展失败: {e}")
        return []

# 导入模型和RAG服务
from app.models import models
from app.services import rag_service
from app.services.faiss_rag_service import search_knowledge_base_with_expanded_query, smart_query_expansion, SentenceTransformer, generate_expanded_queries_ai_only, calculate_query_similarity
from app.services.document_processor import document_processor

# 加载环境变量
load_dotenv()

# 从环境变量获取API密钥和基础URL
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:8000/v1")

def get_embedding_model():
    """获取全局共享的嵌入模型（单例模式）"""
    global _model_cache, _model_lock
    
    if _model_lock is None:
        import threading
        _model_lock = threading.Lock()
    
    if _model_cache is None:
        with _model_lock:
            if _model_cache is None:
                logger.info("初始化全局BGE-M3模型...")
                model_cache_dir = os.getenv("MODEL_CACHE_DIR", "E:\\vscode-py\\model_cache")
                bge_m3_path = os.path.join(model_cache_dir, "models--BAAI--bge-m3")
                _model_cache = SentenceTransformer(bge_m3_path, device="cpu")
                logger.info("全局BGE-M3模型初始化完成")
    
    return _model_cache

def get_relevant_context(db: Session, question: str) -> str:
    """获取相关上下文 - 使用FAISS向量检索"""
    try:
        # 预处理查询
        processed_question = preprocess_query(question)
        if not processed_question:
            return "查询内容无效，请重新输入。"
            
        logger.info(f"开始FAISS RAG检索，原始查询: '{question}'，预处理后: '{processed_question}'")
        
        # 获取AI扩展后的查询用于FAISS检索
        expanded_query = question
        try:
            # 使用全局模型进行查询扩展
            model = get_embedding_model()
            expanded_query = smart_query_expansion(processed_question, model, similarity_threshold=0.8)
            if expanded_query != processed_question:
                logger.info(f"使用AI扩展查询进行FAISS检索: '{processed_question}' -> '{expanded_query}'")
        except Exception as e:
            logger.warning(f"AI查询扩展失败，使用原始查询: {e}")
            expanded_query = processed_question
        
        # 调用FAISS RAG服务，传入已扩展的查询，并禁用FAISS服务内部的扩展功能
        faiss_results = search_knowledge_base_with_expanded_query(expanded_query, k=6)
        
        if faiss_results:
            context_parts = []
            type_stats = {"herb": 0, "prescription": 0, "medic": 0}
            
            for result in faiss_results:
                text = result.get('text', '')
                metadata = result.get('metadata', {})
                score = result.get('score', 0.0)
                doc_type = metadata.get('type', 'unknown')
                
                if doc_type in type_stats:
                    type_stats[doc_type] += 1
                
                if text and score > 0.2:
                    name = metadata.get('name', '未知')
                    # 优先使用权威的数据来源字段
                    authoritative_source = metadata.get('source', None)
                    source_link = metadata.get('source_link', '')
                    
                    if authoritative_source and authoritative_source.strip():
                        # 使用权威数据来源（如"中国药典"）
                        source_info = f"来源: {authoritative_source} - {name}"
                    else:
                        # 权威来源缺失时，标注数据来源未明确
                        source_info = f"来源: 数据来源未明确 - {name}"
                    
                    if source_link:
                        source_info += f"\n链接: {source_link}"
                    
                    context_parts.append(f"{source_info}\n内容: {text}")
            
            if context_parts:
                logger.info(f"FAISS RAG检索成功，返回 {len(context_parts)} 条结果，类型分布: {type_stats}")
                return "\n\n".join(context_parts)
            else:
                logger.warning(f"FAISS RAG检索返回 {len(faiss_results)} 条结果，但全部被过滤（得分 <= 0.2）")
        
        logger.info("FAISS检索无结果，回退到关键词匹配和AI扩展查询")
        
        # 获取AI扩展后的查询用于精确匹配
        expanded_query = question
        try:
            # 使用全局模型进行查询扩展
            model = get_embedding_model()
            expanded_query = smart_query_expansion(processed_question, model, similarity_threshold=0.8)
            if expanded_query != processed_question:
                logger.info(f"使用AI扩展查询进行精确匹配: '{processed_question}' -> '{expanded_query}'")
        except Exception as e:
            logger.warning(f"AI查询扩展失败，使用原始查询: {e}")
            expanded_query = processed_question
        
        # 使用扩展后的查询进行关键词匹配
        knowledge_results = rag_service.query_knowledge(db, expanded_query, limit=3)
        context_parts = []
        
        for result in knowledge_results:
            if isinstance(result, dict):
                content = result.get('content', '')
                source = result.get('source', '')
                if content:
                    context_parts.append(f"来源: {source}\n内容: {content}")
            else:
                context_parts.append(str(result))
        
        # 使用扩展后的查询进行精确匹配
        herbs = db.query(models.Herb).filter(
            models.Herb.name.contains(expanded_query) |
            models.Herb.function.contains(expanded_query) |
            models.Herb.nature.contains(expanded_query) |
            models.Herb.name.contains(question) |  # 保留原始查询匹配
            models.Herb.function.contains(question) |
            models.Herb.nature.contains(question)
        ).limit(2).all()
        
        for herb in herbs:
            herb_info = f"药材: {herb.name}\n性味: {herb.nature or '未知'}\n功效: {herb.function or '未知'}"
            context_parts.append(herb_info)
        
        prescriptions = db.query(models.Prescription).filter(
            models.Prescription.name.contains(expanded_query) |
            models.Prescription.function_indication.contains(expanded_query) |
            models.Prescription.composition.contains(expanded_query) |
            models.Prescription.name.contains(question) |  # 保留原始查询匹配
            models.Prescription.function_indication.contains(question) |
            models.Prescription.composition.contains(question)
        ).limit(2).all()
        
        for prescription in prescriptions:
            prescription_info = f"方剂: {prescription.name}\n组成: {prescription.composition or '未知'}\n功效: {prescription.function_indication or '未知'}"
            context_parts.append(prescription_info)
        
        return "\n\n".join(context_parts) if context_parts else "未找到相关上下文信息。"
        
    except Exception as e:
        print(f"获取上下文时出错: {e}")
        return "上下文检索失败。"

# get_relevant_context_with_expansion 函数已删除，已被 get_relevant_context_with_multi_query 替代
        

        

        
        if faiss_results:
            context_parts = []
            type_stats = {"herb": 0, "prescription": 0, "medic": 0}
            
            for result in faiss_results:
                text = result.get('text', '')
                metadata = result.get('metadata', {})
                score = result.get('score', 0.0)
                doc_type = metadata.get('type', 'unknown')
                
                if doc_type in type_stats:
                    type_stats[doc_type] += 1
                
                if text and score > 0.2:
                    name = metadata.get('name', '未知')
                    # 优先使用权威的数据来源字段
                    authoritative_source = metadata.get('source', None)
                    source_link = metadata.get('source_link', '')
                    
                    if authoritative_source and authoritative_source.strip():
                        # 使用权威数据来源（如"中国药典"）
                        source_info = f"来源: {authoritative_source} - {name}"
                    else:
                        # 权威来源缺失时，标注数据来源未明确
                        source_info = f"来源: 数据来源未明确 - {name}"
                    
                    if source_link:
                        source_info += f"\n链接: {source_link}"
                    
                    context_parts.append(f"{source_info}\n内容: {text}")
            
            if context_parts:
                logger.info(f"FAISS RAG检索成功，返回 {len(context_parts)} 条结果，类型分布: {type_stats}")
                return "\n\n".join(context_parts), expanded_query
            else:
                logger.warning(f"FAISS RAG检索返回 {len(faiss_results)} 条结果，但全部被过滤（得分 <= 0.2）")
        
        logger.info("FAISS检索无结果，回退到关键词匹配和AI扩展查询")
        
        # 使用原始查询 + 扩展查询的组合进行关键词匹配
        combined_query_for_knowledge = f"{question} {expanded_query}" if expanded_query != question else question
        knowledge_results = rag_service.query_knowledge(db, combined_query_for_knowledge, limit=3)
        context_parts = []
        
        for result in knowledge_results:
            if isinstance(result, dict):
                content = result.get('content', '')
                source = result.get('source', '')
                if content:
                    context_parts.append(f"来源: {source}\n内容: {content}")
            else:
                context_parts.append(str(result))
        
        # 使用原始查询 + 扩展查询的组合进行精确匹配
        combined_search_terms = [question]
        if expanded_query != question:
            # 从扩展查询中提取关键词
            import re
            expanded_terms = re.split(r'[？?，,。\s]+', expanded_query)
            combined_search_terms.extend([term.strip() for term in expanded_terms if term.strip() and len(term.strip()) > 1])
        
        # 构建动态查询条件
        herb_conditions = []
        prescription_conditions = []
        
        for term in combined_search_terms:
            herb_conditions.extend([
                models.Herb.name.contains(term),
                models.Herb.function.contains(term),
                models.Herb.nature.contains(term)
            ])
            prescription_conditions.extend([
                models.Prescription.name.contains(term),
                models.Prescription.function_indication.contains(term),
                models.Prescription.composition.contains(term)
            ])
        
        herbs = db.query(models.Herb).filter(*herb_conditions).limit(3).all()
        
        for herb in herbs:
            herb_info = f"药材: {herb.name}\n性味: {herb.nature or '未知'}\n功效: {herb.function or '未知'}"
            context_parts.append(herb_info)
        
        prescriptions = db.query(models.Prescription).filter(*prescription_conditions).limit(3).all()
        
        for prescription in prescriptions:
            prescription_info = f"方剂: {prescription.name}\n组成: {prescription.composition or '未知'}\n功效: {prescription.function_indication or '未知'}"
            context_parts.append(prescription_info)
        
        context_result = "\n\n".join(context_parts) if context_parts else "未找到相关上下文信息。"
        return context_result, expanded_query
        
    except Exception as e:
        print(f"获取上下文时出错: {e}")
        return "上下文检索失败。", question

def get_relevant_context_from_uploaded_docs(question: str, user_id: str = "anonymous", limit: int = 3, specified_doc_id: Optional[str] = None) -> str:
    """
    从上传的文档中检索与问题相关的内容
    使用BGE-M3模型进行语义检索
    支持指定文档ID，只检索指定文档的内容
    只检索指定用户的上传文档
    """
    try:
        # 使用文档处理器进行语义检索
        results = document_processor.search_documents(
            user_id=user_id,
            query=question,
            top_k=limit,
            document_id=specified_doc_id
        )

        if not results:
            return ""

        # 构建上下文字符串，包含文档ID和描述信息
        context_parts = []
        for result in results:
            doc_info = f"文档ID: {result['document_id']}"
            if result['description']:
                doc_info += f"\n描述: {result['description']}"
            context_parts.append(f"{doc_info}\n文件名: {result['filename']}\n内容: {result['text']}")

        return "\n\n".join(context_parts)

    except Exception as e:
        logger.error(f"检索上传文档失败: {e}")
        return ""

def call_ai_model(prompt: str, max_tokens: int = 1000) -> str:
    """调用AI模型"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}" if OPENAI_API_KEY else ""
        }
        
        data = {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        response = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                return "AI模型返回格式错误。"
        else:
            return f"AI服务调用失败，状态码: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return f"AI服务请求错误: {str(e)}"
    except Exception as e:
        return f"AI服务处理错误: {str(e)}"

async def call_ai_model_async(prompt: str, max_tokens: int = 1000) -> str:
    """异步调用AI模型"""
    try:
        import aiohttp
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}" if OPENAI_API_KEY else ""
        }

        data = {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "stream": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if "choices" in result and len(result["choices"]) > 0:
                        return result["choices"][0]["message"]["content"].strip()
                    else:
                        return "AI模型返回格式错误。"
                else:
                    return f"AI服务调用失败，状态码: {response.status}"

    except aiohttp.ClientError as e:
        return f"AI服务请求错误: {str(e)}"
    except Exception as e:
        return f"AI服务处理错误: {str(e)}"

async def call_ai_model_stream(prompt: str, max_tokens: int = 1200):
    """调用AI模型（流式返回）
    
    使用原生API的流式功能，逐步返回AI生成的文本
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}" if OPENAI_API_KEY else ""
        }

        data = {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens,
            "stream": True
        }

        response = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=data,
            stream=True,
            timeout=30
        )

        if response.status_code == 200:
            # 处理流式响应
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        else:
            yield f"AI服务调用失败，状态码: {response.status_code}"

    except requests.exceptions.RequestException as e:
        logger.error(f"流式AI请求错误: {str(e)}")
        yield f"AI服务请求错误: {str(e)}"
    except Exception as e:
        logger.error(f"流式AI处理错误: {str(e)}")
        yield f"AI服务处理错误: {str(e)}"

async def get_relevant_context_with_multi_query_stream(db: Session, question: str):
    """
    流式获取相关上下文，支持渐进式结果返回：
    1. 首先返回原始查询的检索结果（只返回最匹配的1个）
    2. 然后逐个返回每个扩展查询的检索结果（最多2个扩展查询，每个只返回1个结果）
    返回友好的用户体验格式，不显示技术性标题和相似度信息
    增强版本：根据用户查询意图过滤结果类型
    """
    try:
        logger.info(f"开始流式多查询RAG检索，原始查询: '{question}'")
        
        # 检测用户是否询问特定类型
        is_prescription_query = any(keyword in question for keyword in ["方剂", "方", "药方", "汤", "散", "丸"])
        is_medic_query = any(keyword in question for keyword in ["中成药", "成药", "药片", "胶囊", "颗粒", "口服液"])
        is_herb_query = any(keyword in question for keyword in ["药材", "中药", "草药"])
        
        # 确定需要的类型和是否需要平衡检索
        target_type = None
        use_balanced = True
        
        if is_prescription_query and not is_medic_query:
            target_type = "prescription"
            use_balanced = False
            logger.info("检测到用户明确询问方剂，将只返回方剂类型结果")
        elif is_medic_query and not is_prescription_query:
            target_type = "medic"
            use_balanced = False
            logger.info("检测到用户明确询问中成药，将只返回中成药类型结果")
        elif is_herb_query:
            target_type = "herb"
            use_balanced = False
            logger.info("检测到用户明确询问药材，将只返回药材类型结果")
        else:
            use_balanced = True
            logger.info("未检测到明确类型询问，使用平衡检索返回多种类型结果")
        
        # 第一步：AI扩充原问题（限制最多2个扩展查询）
        expanded_queries = []
        try:
            # 使用全局模型
            model = get_embedding_model()
            
            # 获取AI生成的扩展查询列表
            ai_expanded_queries = generate_expanded_queries_ai_only(question)
            
            # 第二步：对每个扩充的问题与原问题做相似度计算，防止AI的语义偏差
            for expanded_query in ai_expanded_queries:
                similarity = calculate_query_similarity(question, expanded_query, model)
                if similarity >= 0.6:  # 相似度阈值
                    expanded_queries.append(expanded_query)
                    logger.info(f"AI扩展查询通过验证: '{expanded_query}' (相似度: {similarity:.3f})")
                    
                    # 限制最多2个扩展查询
                    if len(expanded_queries) >= 2:
                        break
                        
                else:
                    logger.debug(f"AI扩展查询被过滤: '{expanded_query}' (相似度: {similarity:.3f} < 0.6)")
                    
        except Exception as e:
            logger.warning(f"AI查询扩展失败，仅使用原始查询: {e}")
        
        logger.info(f"合格的扩展查询数量: {len(expanded_queries)}, 内容: {expanded_queries}")
        
        # 第三步：对原始查询和每个合格的扩展查询分别进行独立FAISS检索
        all_queries = [question] + expanded_queries
        all_results = []
        
        # 对每个查询进行独立检索（每个查询只返回最匹配的1个结果）
        for i, query in enumerate(all_queries):
            query_type = "原始查询" if i == 0 else f"扩展查询_{i}"
            logger.info(f"执行独立检索 - {query_type}: '{query}'")
            
            # 根据用户意图选择检索方法
            if use_balanced:
                # 使用平衡检索返回多种类型结果
                faiss_results = search_knowledge_base_balanced(query, k=1)
            else:
                # 使用指定类型的检索
                faiss_results = search_knowledge_base_with_expanded_query(query, k=1)
            
            # 为每个结果标记来源查询
            for result in faiss_results:
                result["query_source"] = query_type
                result["source_query"] = query
                # 根据用户意图过滤结果类型
                if target_type:
                    source_type = result.get('metadata', {}).get('type', 'unknown')
                    if source_type != target_type:
                        logger.debug(f"流式过滤掉不符合用户意图的类型: {source_type}, 用户需要: {target_type}")
                        continue
                all_results.append(result)
        
        # 处理检索结果 - 合并、去重、排序
        results = []
        seen_content = set()  # 用于去重
        
        # 按得分排序所有结果
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        for result in all_results:
            text = result.get('text', '')
            metadata = result.get('metadata', {})
            score = result.get('score', 0.0)
            
            if text and score > 0.1:  # 降低阈值以确保结果完整性
                # 创建唯一标识用于去重
                content_key = f"{text[:100]}_{metadata.get('name', '')}_{metadata.get('type', '')}"
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    
                    source_type = metadata.get('type', 'unknown')
                    name = metadata.get('name', '未知')
                    # 优先使用权威的数据来源字段
                    authoritative_source = metadata.get('source', None)
                    
                    # 根据类型正确标注方剂或中成药
                    if source_type == "prescription":
                        type_label = "方剂"
                    elif source_type == "medic":
                        type_label = "中成药"
                    else:
                        type_label = "药材"
                    
                    if authoritative_source and authoritative_source.strip():
                        # 使用权威数据来源（如"中国药典"）
                        source_info = f"来源: {authoritative_source} - {name}（{type_label}）"
                    else:
                        # 权威来源缺失时，标注数据来源未明确
                        source_info = f"来源: 数据来源未明确 - {name}（{type_label}）"
                    
                    full_content = f"{source_info}\n内容: {text}"
                    
                    results.append({
                        "content": full_content,
                        "score": score,
                        "source_type": source_type,
                        "name": name,
                        "query_source": result.get("query_source", "未知"),
                        "source_query": result.get("source_query", ""),
                        "type_label": type_label
                    })
        
        # 构建上下文
        context_parts = []
        
        # 按类型分组整理结果
        grouped_results = {}
        for result in results:
            source_type = result["source_type"]
            if source_type not in grouped_results:
                grouped_results[source_type] = []
            grouped_results[source_type].append(result)
        
        # 根据用户意图调整优先级顺序
        if target_type:
            # 用户明确指定了类型，优先该类型
            type_order = [target_type]
            # 添加其他相关类型（如果有）
            if target_type == "prescription":
                type_order.extend(["herb"])  # 方剂相关药材
            elif target_type == "medic":
                type_order.extend(["herb"])  # 中成药相关药材
            elif target_type == "herb":
                type_order.extend(["prescription", "medic"])  # 药材相关的方剂和中成药
        else:
            # 泛指情况，按默认优先级
            type_order = ["prescription", "herb", "medic"]
        
        other_types = [t for t in grouped_results.keys() if t not in type_order]
        all_types = type_order + other_types
        
        # 添加意图说明到上下文开头（如果用户明确指定了类型）
        if target_type:
            intent_desc = {
                "prescription": "用户明确要求推荐传统方剂",
                "medic": "用户明确要求推荐中成药", 
                "herb": "用户明确要求推荐药材"
            }.get(target_type, "")
            if intent_desc:
                context_parts.append(f"【查询意图说明】{intent_desc}\n")
        
        for source_type in all_types:
            if source_type in grouped_results:
                # 直接添加内容，不添加技术性标题
                results_list = grouped_results[source_type]
                # 按得分排序
                results_list.sort(key=lambda x: -x["score"])
                
                for result in results_list:
                    # 直接添加内容，不添加技术性标题、相似度信息或分隔符
                    context_parts.append(result['content'])
        
        final_context = "\n\n".join(context_parts) if context_parts else "未找到相关上下文信息。"
        
        # 返回最终结果
        yield "final_context", final_context, question
        
    except Exception as e:
        error_msg = f"获取流式多查询上下文时出错: {e}"
        logger.error(error_msg)
        yield "error", "上下文检索失败。", question

def get_relevant_context_with_multi_query(db: Session, question: str) -> tuple[str, str]:
    """
    获取相关上下文，正确实现三步逻辑：
    1. AI扩充原问题
    2. 扩充的问题与原问题做相似度计算防止AI的语义偏差
    3. 原问题与合格的扩充问题组合后检索知识库内容
    """
    try:
        # 预处理查询
        processed_question = preprocess_query(question)
        if not processed_question:
            return "查询内容无效，请重新输入。", question
            
        logger.info(f"开始多查询RAG检索，原始查询: '{question}'，预处理后: '{processed_question}'")
        
        # 检测用户是否询问特定类型
        is_prescription_query = any(keyword in question for keyword in ["方剂", "方", "药方", "汤", "散", "丸"])
        is_medic_query = any(keyword in question for keyword in ["中成药", "成药", "药片", "胶囊", "颗粒", "口服液"])
        is_herb_query = any(keyword in question for keyword in ["药材", "中药", "草药"])
        
        # 确定需要的类型和是否需要平衡检索
        target_type = None
        use_balanced = True
        
        if is_prescription_query and not is_medic_query:
            target_type = "prescription"
            use_balanced = False
            logger.info("检测到用户明确询问方剂，将只返回方剂类型结果")
        elif is_medic_query and not is_prescription_query:
            target_type = "medic"
            use_balanced = False
            logger.info("检测到用户明确询问中成药，将只返回中成药类型结果")
        elif is_herb_query:
            target_type = "herb"
            use_balanced = False
            logger.info("检测到用户明确询问药材，将只返回药材类型结果")
        else:
            use_balanced = True
            logger.info("未检测到明确类型询问，使用平衡检索返回多种类型结果")
        
        # 第一步：AI扩充原问题
        expanded_queries = []
        try:
            # 使用全局模型
            model = get_embedding_model()
            
            # 获取AI生成的扩展查询列表
            ai_expanded_queries = generate_expanded_queries_ai_only(processed_question)
            
            # 第二步：对每个扩充的问题与原问题做相似度计算，防止AI的语义偏差
            for expanded_query in ai_expanded_queries:
                similarity = calculate_query_similarity(processed_question, expanded_query, model)
                if similarity >= 0.8:  # 相似度阈值
                    expanded_queries.append(expanded_query)
                    logger.info(f"AI扩展查询通过验证: '{expanded_query}' (相似度: {similarity:.3f})")
                else:
                    logger.debug(f"AI扩展查询被过滤: '{expanded_query}' (相似度: {similarity:.3f} < 0.8)")
                    
        except Exception as e:
            logger.warning(f"AI查询扩展失败，仅使用原始查询: {e}")
        
        logger.info(f"合格的扩展查询数量: {len(expanded_queries)}, 内容: {expanded_queries}")
        
        # 第三步：将原问题与合格的扩充问题组合，一起用于检索知识库
        all_valid_queries = [question] + expanded_queries
        
        # 构建综合查询（用于FAISS检索）
        combined_query = " ".join(all_valid_queries)
        
        # 根据用户意图选择合适的检索方法
        if use_balanced:
            # 使用平衡检索返回多种类型结果
            faiss_results = search_knowledge_base_balanced(combined_query, k=8)
        else:
            # 使用指定类型的检索，只返回目标类型结果
            faiss_results = search_knowledge_base_with_expanded_query(combined_query, k=8)
        
        # 处理检索结果
        results = []
        seen_content = set()  # 用于去重
        
        for result in faiss_results:
            text = result.get('text', '')
            metadata = result.get('metadata', {})
            score = result.get('score', 0.0)
            
            if text and score > 0.2:
                source_type = metadata.get('type', 'unknown')
                
                # 根据用户意图过滤结果
                if target_type and source_type != target_type:
                    logger.debug(f"过滤掉不符合用户意图的类型: {source_type}, 用户需要: {target_type}")
                    continue
                
                # 创建唯一标识用于去重
                content_key = f"{text[:100]}_{metadata.get('name', '')}_{source_type}"
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    
                    name = metadata.get('name', '未知')
                    # 优先使用权威的数据来源字段
                    authoritative_source = metadata.get('source', None)
                                    
                    # 根据类型正确标注方剂或中成药
                    if source_type == "prescription":
                        type_label = "方剂"
                    elif source_type == "medic":
                        type_label = "中成药"
                    else:
                        type_label = "药材"
                    
                    if authoritative_source and authoritative_source.strip():
                        # 使用权威数据来源（如"中国药典"）
                        source_info = f"来源: {authoritative_source} - {name}（{type_label}）"
                    else:
                        # 权威来源缺失时，标注数据来源未明确
                        source_info = f"来源: 数据来源未明确 - {name}（{type_label}）"
                    full_content = f"{source_info}\n内容: {text}"
                    
                    results.append({
                        "content": full_content,
                        "score": score,
                        "source_type": source_type,
                        "name": name,
                        "type_label": type_label  # 添加类型标签
                    })
        
        # 构建上下文
        context_parts = []
        
        # 按类型分组整理结果
        grouped_results = {}
        for result in results:
            source_type = result["source_type"]
            if source_type not in grouped_results:
                grouped_results[source_type] = []
            grouped_results[source_type].append(result)
        
        # 根据用户意图调整优先级顺序
        if target_type:
            # 用户明确指定了类型，优先该类型
            type_order = [target_type]
            # 添加其他相关类型（如果有）
            if target_type == "prescription":
                type_order.extend(["herb"])  # 方剂相关药材
            elif target_type == "medic":
                type_order.extend(["herb"])  # 中成药相关药材
            elif target_type == "herb":
                type_order.extend(["prescription", "medic"])  # 药材相关的方剂和中成药
        else:
            # 泛指情况，按默认优先级
            type_order = ["prescription", "herb", "medic"]
        
        other_types = [t for t in grouped_results.keys() if t not in type_order]
        all_types = type_order + other_types
        
        # 添加意图说明到上下文开头（如果用户明确指定了类型）
        if target_type:
            intent_desc = {
                "prescription": "用户明确要求推荐传统方剂",
                "medic": "用户明确要求推荐中成药", 
                "herb": "用户明确要求推荐药材"
            }.get(target_type, "")
            if intent_desc:
                context_parts.append(f"【查询意图说明】{intent_desc}\n")
        
        for source_type in all_types:
            if source_type in grouped_results:
                # 直接添加内容，不添加技术性标题
                results_list = grouped_results[source_type]
                # 按得分排序
                results_list.sort(key=lambda x: -x["score"])
                
                for result in results_list:
                    # 直接添加内容，不添加技术性标题、相似度信息或分隔符
                    context_parts.append(result['content'])
        
        final_context = "\n\n".join(context_parts) if context_parts else "未找到相关上下文信息。"
        
        # 返回扩展查询字符串（用于前端显示）
        expanded_query_str = " | ".join(expanded_queries) if expanded_queries else question
        
        return final_context, expanded_query_str
        
    except Exception as e:
        print(f"获取多查询上下文时出错: {e}")
        return "上下文检索失败。", question

def get_relevant_context_simple(db: Session, question: str) -> tuple[str, str]:
    """
    获取相关上下文 - 简化版本，直接使用原始查询进行检索，不进行AI扩展
    """
    try:
        # 预处理查询
        processed_question = preprocess_query(question)
        if not processed_question:
            return "查询内容无效，请重新输入。", question
            
        logger.info(f"开始简化RAG检索，原始查询: '{question}'，预处理后: '{processed_question}'")
        
        # 直接使用预处理后的查询进行FAISS检索，禁用FAISS服务内部的扩展功能
        faiss_results = search_knowledge_base_with_expanded_query(processed_question, k=8)
        
        # 处理检索结果
        results = []
        seen_content = set()  # 用于去重
        
        for result in faiss_results:
            text = result.get('text', '')
            metadata = result.get('metadata', {})
            score = result.get('score', 0.0)
            
            if text and score > 0.2:
                # 创建唯一标识用于去重
                content_key = f"{text[:100]}_{metadata.get('name', '')}_{metadata.get('type', '')}"
                if content_key not in seen_content:
                    seen_content.add(content_key)
                    
                    name = metadata.get('name', '未知')
                    source_type = metadata.get('type', 'unknown')
                    # 优先使用权威的数据来源字段
                    authoritative_source = metadata.get('source', None)
                                    
                    if authoritative_source and authoritative_source.strip():
                        # 使用权威数据来源（如"中国药典"）
                        source_info = f"来源: {authoritative_source} - {name}"
                    else:
                        # 权威来源缺失时，标注数据来源未明确
                        source_info = f"来源: 数据来源未明确 - {name}"
                    full_content = f"{source_info}\n内容: {text}"
                    
                    results.append({
                        "content": full_content,
                        "score": score,
                        "source_type": source_type,
                        "name": name
                    })
        
        # 构建上下文
        context_parts = []
        
        # 按类型分组整理结果
        grouped_results = {}
        for result in results:
            source_type = result["source_type"]
            if source_type not in grouped_results:
                grouped_results[source_type] = []
            grouped_results[source_type].append(result)
        
        # 按优先级排序：prescription, herb, medic
        type_order = ["prescription", "herb", "medic"]
        other_types = [t for t in grouped_results.keys() if t not in type_order]
        all_types = type_order + other_types
        
        for source_type in all_types:
            if source_type in grouped_results:
                # 直接添加内容，不添加技术性标题
                results_list = grouped_results[source_type]
                # 按得分排序
                results_list.sort(key=lambda x: -x["score"])
                
                for result in results_list:
                    # 直接添加内容，不添加技术性标题、相似度信息或分隔符
                    context_parts.append(result['content'])
        
        final_context = "\n\n".join(context_parts) if context_parts else "未找到相关上下文信息。"
        
        # 返回原始查询字符串（不再有扩展查询）
        return final_context, processed_question
        
    except Exception as e:
        print(f"获取简化上下文时出错: {e}")
        return "上下文检索失败。", question

async def chat_with_context(question: str, context: Optional[str], db: Session, conversation_history: Optional[List[Dict]] = None, user_id: str = "anonymous", return_expansion: bool = False) -> str:
    """基于上下文的AI对话（支持对话历史）"""
    try:
        # 预处理用户查询
        processed_question = preprocess_query(question)
        if not processed_question:
            if return_expansion:
                return "查询内容无效，请重新输入。", question
            else:
                return "查询内容无效，请重新输入。"
                
        expanded_query = processed_question
        
        # 如果没有提供上下文，优先从上传的文档中检索，然后从知识库检索
        if not context:
            # 首先从上传的文档中检索相关内容（只检索当前用户的文档）
            uploaded_docs_context = get_relevant_context_from_uploaded_docs(processed_question, user_id, limit=3)
            
            # 然后从知识库中检索相关内容（简化检索，不进行AI扩展）
            knowledge_context, expanded_query = get_relevant_context_simple(db, processed_question)
            
            # 优先使用上传文档的内容，如果有的话
            if uploaded_docs_context:
                context = f"【基于您上传的文件内容】\n{uploaded_docs_context}"
                # 如果知识库也有相关内容，可以附加（可选）
                if knowledge_context:
                    context += f"\n\n【来自中医药知识库】\n{knowledge_context}"
            else:
                # 如果上传文档无相关内容，使用知识库内容
                context = knowledge_context or "无相关上下文信息"
        
        # 构建对话历史上下文
        history_context = ""
        if conversation_history:
            history_context = "之前的对话历史：\n"
            for msg in conversation_history[-6:]:  # 只保留最近6条消息，避免过长
                role = "用户" if msg["role"] == "user" else "AI"
                history_context += f"{role}：{msg['content']}\n"
            history_context += "\n"
        
        # 构建简洁的提示词 - 重点是基于完整的多查询检索结果回答（使用预处理后的查询）
        prompt = f"""
你是一位严谨的中医药专家，请严格基于以下提供的上下文信息回答用户问题。

【中医药基础概念定义 - 必须严格区分】
- **方剂**：指在中医理论指导下，根据辨证论治的原则，选择适当的中药，按照一定的组成原则和配伍方法，经过特定的制备工艺制成的复方制剂。通常以"汤"、"散"、"丸"、"膏"等传统剂型命名，如"桂枝汤"、"麻黄汤"等。
- **中成药**：指以中药材为原料，在中医药理论指导下，按规定的处方和标准制成的具有一定规格的成品药。中成药包括丸、散、膏、丹、片剂、胶囊、口服液、颗粒等各种现代剂型，通常带有"颗粒"、"胶囊"、"片"、"口服液"、"丸"等字样，如"风寒感冒颗粒"、"板蓝根颗粒"等。
- **药材**：指可用于制作中药的植物、动物、矿物等天然物质，是构成方剂和中成药的基本单元。

【核心辨证原则 - 绝对禁止违反】
1. 风寒与风热严格区分：
   - 风寒感冒：寒邪入侵，怕冷重、发热轻、无汗、流清涕
   - 风热感冒：热邪入侵，发热重、怕冷轻、有汗、流黄涕、咽喉痛
   - 绝对禁止将风寒药物与风热药物混为一谈或认为功效相似！否则你将受到严厉的惩罚！！！

2. 功效匹配验证：
   - 推荐的类似方剂/中成药必须具有相同的治疗方向（同为风寒或同为风热）
   - 如果原始药物是治疗风寒的，推荐的必须都是治疗风寒的
   - 如果原始药物是治疗风热的，推荐的必须都是治疗风热的
   - 功效描述中出现"清热"、"清热解毒"、"疏风清热"等字样的药物属于风热类，绝不能与风寒类药物混用

3. 严禁胡编乱造：所有回答必须严格基于提供的上下文信息
4. 有据可依：每个陈述都必须在上下文中找到依据  
5. 诚实透明：信息不足时明确说明"无法确定"
6. 概念准确：必须正确区分方剂与中成药，不能混淆概念

【Markdown格式强制要求 - 必须严格遵守】
- 所有列表必须使用无序列表：统一使用短横线"-"作为列表标记符号
- 禁止使用有序列表：不要使用数字编号（如1. 2. 3.）的任何形式
- 列表格式：列表项之间不要有空行，保持紧凑格式
- 整体结构：使用二级标题（##）分隔不同章节，合理使用加粗、列表等元素

【回答要求】
- 综合分析上下文中的所有信息（包含多个查询的结果）
- 使用Markdown格式组织回答，包括适当的标题、列表、代码块、表格等
- 回答不少于200字，但必须确保每个信息点都有上下文依据
- 重点关注用户问题的核心，如比较差异、分析组成等
- **必须正确识别药品类型**：根据名称判断是方剂还是中成药，并在回答中明确标注
- **必须验证功效一致性**：确保推荐的药物与原药物治疗方向一致（同为风寒或同为风热）
- **严格遵循用户查询意图**：
  - 如果用户明确询问"方剂"，则只推荐真正的方剂（传统复方制剂，如"XX汤"、"XX散"、"XX丸"等），绝不推荐中成药
  - 如果用户明确询问"中成药"，则只推荐中成药（现代成品药，如"XX颗粒"、"XX胶囊"、"XX片"等），绝不推荐传统方剂  
  - 如果用户询问"药物"或"药品"等泛指词汇，则可以同时推荐方剂和中成药，但必须明确标注每种的类型
- **绝对禁止混淆概念**：严禁将中成药称为方剂，或将方剂称为中成药
- **严格遵循以下格式规范**：
  - 在列举药品时，必须使用格式：`- **[药品名称]**（[方剂/中成药]）`
  - 例如：`- **风寒感冒颗粒**（中成药）` 或 `- **麻黄汤**（方剂）`
  - **绝对禁止**将中成药称为"方剂"或将方剂称为"中成药"
  - 如果不确定药品类型，必须查看上下文中的类型标注，不得自行猜测

{history_context}上下文信息：
{context}

用户问题：{processed_question}

请用中文回答，严格基于上述上下文信息。
"""
        
        response = call_ai_model(prompt, max_tokens=1200)
        
        if return_expansion:
            return response, expanded_query
        else:
            return response
        
    except Exception as e:
        error_msg = f"AI对话处理错误: {str(e)}"
        print(error_msg)
        if return_expansion:
            return "抱歉，AI服务暂时不可用，请稍后再试。", question
        else:
            return "抱歉，AI服务暂时不可用，请稍后再试。"

async def chat_with_context_stream(question: str, context: Optional[str], db: Session, conversation_history: Optional[List[Dict]] = None, user_id: str = "anonymous"):
    """基于上下文的AI对话（流式返回）"""
    try:
        # 预处理用户查询
        processed_question = preprocess_query(question)
        if not processed_question:
            yield "查询内容无效，请重新输入。"
            return
            
        expanded_query = processed_question

        # 如果没有提供上下文，优先从上传的文档中检索，然后从知识库检索
        if not context:
            # 检查用户是否指定了特定文档
            specified_doc_id = None
            user_docs = document_processor.get_user_documents(user_id)
            
            if user_docs:
                # 使用AI识别用户是否指定了特定文档（使用预处理后的查询）
                doc_names = [f"{doc['filename']}" + (f"({doc['description']})" if doc.get('description') else "") for doc in user_docs]
                doc_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(doc_names)])
                
                # 构建识别提示（使用预处理后的查询）
                identify_prompt = f"""
用户上传了以下文档：
{doc_list}

用户问题：{processed_question}

请判断用户是否指定了要基于某个特定文档回答问题。
如果是，请返回文档ID；如果不是，请返回"NONE"。
只返回文档ID或"NONE"，不要返回其他内容。
"""
                
                try:
                    # 调用AI识别文档
                    doc_id_response = await call_ai_model_async(identify_prompt, max_tokens=50)
                    doc_id_response = doc_id_response.strip()
                    
                    # 检查返回的文档ID是否有效
                    if doc_id_response != "NONE" and doc_id_response in [doc['document_id'] for doc in user_docs]:
                        specified_doc_id = doc_id_response
                        logger.info(f"用户指定了文档: {specified_doc_id}")
                except Exception as e:
                    logger.warning(f"文档识别失败: {e}")
            
            # 并行检索：同时从上传文档和知识库中检索相关内容（使用预处理后的查询）
            uploaded_docs_context = get_relevant_context_from_uploaded_docs(processed_question, user_id, limit=3)
            
            # 然后从知识库中检索相关内容（简化检索，不进行AI扩展）
            knowledge_context, expanded_query = get_relevant_context_simple(db, processed_question)
            
            # 优先使用上传文档的内容，如果有的话
            if uploaded_docs_context:
                if specified_doc_id:
                    context = f"【基于您指定的文档】\n{uploaded_docs_context}"
                else:
                    context = f"【基于您上传的文件内容】\n{uploaded_docs_context}"
                # 如果知识库也有相关内容，可以附加（可选）
                if knowledge_context:
                    context += f"\n\n【来自中医药知识库】\n{knowledge_context}"
            else:
                # 如果上传文档无相关内容，使用知识库内容
                context = knowledge_context or "无相关上下文信息"

        # 构建对话历史上下文
        history_context = ""
        if conversation_history:
            history_context = "之前的对话历史：\n"
            for msg in conversation_history[-6:]:  # 只保留最近6条消息，避免过长
                role = "用户" if msg["role"] == "user" else "AI"
                history_context += f"{role}：{msg['content']}\n"
            history_context += "\n"

        # 构建简洁的提示词 - 重点是基于完整的多查询检索结果回答（使用预处理后的查询）
        prompt = f"""
你是一位严谨的中医药专家，请严格基于以下提供的上下文信息回答用户问题。

【中医药基础概念定义 - 必须严格区分】
- **方剂**：指在中医理论指导下，根据辨证论治的原则，选择适当的中药，按照一定的组成原则和配伍方法，经过特定的制备工艺制成的复方制剂。通常以"汤"、"散"、"丸"、"膏"等传统剂型命名，如"桂枝汤"、"麻黄汤"等。
- **中成药**：指以中药材为原料，在中医药理论指导下，按规定的处方和标准制成的具有一定规格的成品药。中成药包括丸、散、膏、丹、片剂、胶囊、口服液、颗粒等各种现代剂型，通常带有"颗粒"、"胶囊"、"片"、"口服液"、"丸"等字样，如"风寒感冒颗粒"、"板蓝根颗粒"等。
- **药材**：指可用于制作中药的植物、动物、矿物等天然物质，是构成方剂和中成药的基本单元。

【核心辨证原则 - 绝对禁止违反】
1. 风寒与风热严格区分：
   - 风寒感冒：恶寒重、发热轻、无汗、流清涕、咳白痰、舌苔薄白、脉浮紧
   - 风热感冒：发热重、恶寒轻、有汗、流黄涕、咳黄痰、咽喉肿痛、舌红苔黄
   - 绝对禁止将风寒药物与风热药物混为一谈或认为功效相似！

2. 功效匹配验证：
   - 推荐的类似方剂/中成药必须具有相同的治疗方向（同为风寒或同为风热）
   - 如果原始药物是治疗风寒的，推荐的必须都是治疗风寒的
   - 如果原始药物是治疗风热的，推荐的必须都是治疗风热的
   - 功效描述中出现"清热"、"清热解毒"、"疏风清热"等字样的药物属于风热类，绝不能与风寒类药物混用

3. 严禁胡编乱造：所有回答必须严格基于提供的上下文信息
4. 有据可依：每个陈述都必须在上下文中找到依据  
5. 诚实透明：信息不足时明确说明"无法确定"
6. 概念准确：必须正确区分方剂与中成药，不能混淆概念

【Markdown格式强制要求 - 必须严格遵守】
- 所有列表必须使用无序列表：统一使用短横线"-"作为列表标记符号
- 禁止使用有序列表：不要使用数字编号（如1. 2. 3.）的任何形式
- 列表格式：列表项之间不要有空行，保持紧凑格式
- 整体结构：使用二级标题（##）分隔不同章节，合理使用加粗、列表等元素

【回答要求】
- 综合分析上下文中的所有信息（包含多个查询的结果）
- 使用Markdown格式组织回答，包括适当的标题、列表、代码块、表格等
- 回答不少于200字，但必须确保每个信息点都有上下文依据
- 重点关注用户问题的核心，如比较差异、分析组成等
- **必须正确识别药品类型**：根据名称判断是方剂还是中成药，并在回答中明确标注
- **必须验证功效一致性**：确保推荐的药物与原药物治疗方向一致（同为风寒或同为风热）
- **严格遵循用户查询意图**：
  - 如果用户明确询问"方剂"，则只推荐真正的方剂（传统复方制剂，如"XX汤"、"XX散"、"XX丸"等），绝不推荐中成药
  - 如果用户明确询问"中成药"，则只推荐中成药（现代成品药，如"XX颗粒"、"XX胶囊"、"XX片"等），绝不推荐传统方剂  
  - 如果用户询问"药物"或"药品"等泛指词汇，则可以同时推荐方剂和中成药，但必须明确标注每种的类型
- **绝对禁止混淆概念**：严禁将中成药称为方剂，或将方剂称为中成药
- **严格遵循以下格式规范**：
  - 在列举药品时，必须使用格式：`- **[药品名称]**（[方剂/中成药]）`
  - 例如：`- **风寒感冒颗粒**（中成药）` 或 `- **麻黄汤**（方剂）`
  - **绝对禁止**将中成药称为"方剂"或将方剂称为"中成药"
  - 如果不确定药品类型，必须查看上下文中的类型标注，不得自行猜测

{history_context}上下文信息：
{context}

用户问题：{processed_question}

请用中文回答，严格基于上述上下文信息。
"""

        # 使用流式AI调用
        async for chunk in call_ai_model_stream(prompt, max_tokens=1200):
            yield chunk
                
    except Exception as e:
        error_msg = f"AI对话处理错误: {str(e)}"
        logger.error(error_msg)
        yield "抱歉，AI服务暂时不可用，请稍后再试。"

async def generate_explanation(content_type: str, content: str, db: Session) -> str:
    """生成详细解释"""
    try:
        # 获取相关内容上下文
        context = get_relevant_context(db, content)
        
        prompt = f"""
你是一位专业的中医药专家，请为以下{content_type}生成详细的中医药学解释：

内容：{content}

相关上下文：
{context}

请从中医药理论角度，详细解释其性味归经、功效主治、配伍应用、使用注意等方面，
要求内容专业、准确、全面，用中文回答。
**重要：请使用Markdown格式组织你的回答，包括适当的标题、列表、代码块、表格等格式化元素，以便于阅读和展示。**
"""
        
        response = call_ai_model(prompt, max_tokens=1000)
        return response
        
    except Exception as e:
        error_msg = f"解释生成错误: {str(e)}"
        print(error_msg)
        return "抱歉，解释生成功能暂时不可用。"

async def recommend_prescriptions(symptoms: str, db: Session) -> List[Dict]:
    """根据症状推荐方剂"""
    try:
        # 检索相关方剂
        prescriptions = db.query(models.Prescription).filter(
            models.Prescription.function_indication.contains(symptoms)
        ).limit(5).all()
        
        if not prescriptions:
            # 如果没有直接匹配，使用AI生成推荐
            context = get_relevant_context(db, symptoms)
            prompt = f"""
你是一位经验丰富的中医师，患者主诉症状为：{symptoms}

请基于中医辨证论治原则，推荐3个适合的经典方剂，每个方剂需包含：
1. 方剂名称
2. 主要组成
3. 功效主治
4. 适用证型

相关参考信息：
{context}

**重要：请使用Markdown格式组织你的回答，包括适当的标题、列表、代码块、表格等格式化元素，以便于阅读和展示。**
"""
            
            response = call_ai_model(prompt, max_tokens=800)
            
            return [{"name": "AI推荐", "recommendation": response}]
        
        # 返回数据库中的方剂
        recommendations = []
        for prescription in prescriptions:
            recommendations.append({
                "name": prescription.name,
                "composition": prescription.composition or "组成信息暂缺",
                "function": prescription.function_indication or "功效信息暂缺",
                "source": prescription.source or "来源信息暂缺"
            })
        
        return recommendations
        
    except Exception as e:
        error_msg = f"方剂推荐错误: {str(e)}"
        print(error_msg)
        return [{"name": "推荐失败", "recommendation": "方剂推荐功能暂时不可用"}]

async def analyze_composition(composition: str, db: Session) -> Dict:
    """分析方剂组成和功效"""
    try:
        context = get_relevant_context(db, composition)
        
        prompt = f"""
你是一位中医药专家，请分析以下方剂组成：

方剂组成：{composition}

相关上下文：
{context}

请分析：
1. 各药材的性味归经和功效
2. 整体方剂的君臣佐使配伍关系
3. 主要功效和适应症
4. 配伍特点和注意事项

用中文详细回答。
**重要：请使用Markdown格式组织你的回答，包括适当的标题、列表、代码块、表格等格式化元素，以便于阅读和展示。**
"""
        
        analysis = call_ai_model(prompt, max_tokens=1000)
        
        return {
            "analysis": analysis,
            "composition": composition
        }
        
    except Exception as e:
        error_msg = f"组成分析错误: {str(e)}"
        print(error_msg)
        return {
            "analysis": "组成分析功能暂时不可用",
            "composition": composition
        }

async def get_embedding(text: str) -> List[float]:
    """获取文本嵌入向量"""
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        
        # 这里简化处理，实际项目中应该使用配置的embedding模型
        # 由于主要使用Qwen模型，这里返回模拟向量
        # 在实际部署中，可以集成sentence-transformers
        
        # 模拟向量（768维）
        import hashlib
        hash_object = hashlib.md5(text.encode())
        hash_hex = hash_object.hexdigest()
        vector = [ord(c) / 255.0 for c in hash_hex[:768]]
        # 补齐到768维
        while len(vector) < 768:
            vector.append(0.0)
        return vector[:768]
        
    except Exception as e:
        print(f"嵌入向量生成错误: {e}")
        return [0.0] * 768

# 全局文件存储（实际项目中应使用数据库）
_uploaded_documents = {}

def get_chat_history_key(user_id: str) -> str:
    """获取用户聊天历史的Redis键"""
    return f"chat_history:{user_id}"

def get_conversation_history_key(user_id: str) -> str:
    """获取用户完整对话历史的Redis键"""
    return f"conversation_history:{user_id}"

def get_current_conversation_key(user_id: str) -> str:
    """获取用户当前对话的Redis键"""
    return f"current_conversation:{user_id}"

async def save_conversation_pair(user_id: str, question: str, answer: str):
    """保存完整的问答对话对到Redis（用于历史记录）"""
    try:
        from app.cache.redis_cache import redis_client
        
        # 保存到完整历史记录
        history_key = get_conversation_history_key(user_id)
        existing_history = redis_client.get(history_key) or []
        
        conversation_pair = {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        existing_history.append(conversation_pair)
        
        # 只保留最近100个对话对
        if len(existing_history) > 100:
            existing_history = existing_history[-100:]
        
        redis_client.set(history_key, existing_history, ttl=2592000)  # 30天过期
        
        # 同时保存到当前对话
        current_key = get_current_conversation_key(user_id)
        current_conversation = redis_client.get(current_key) or []
        current_conversation.append(conversation_pair)
        redis_client.set(current_key, current_conversation, ttl=86400)  # 24小时过期
        
        return True
    except Exception as e:
        print(f"保存对话历史失败: {e}")
        return False

async def get_conversation_history(user_id: str, limit: int = 50) -> list:
    """获取用户的完整对话历史（所有对话记录）"""
    try:
        from app.cache.redis_cache import redis_client
        history_key = get_conversation_history_key(user_id)
        history = redis_client.get(history_key) or []
        return history[-limit:] if limit else history
    except Exception as e:
        print(f"获取对话历史失败: {e}")
        return []

async def get_current_conversation(user_id: str) -> list:
    """获取用户的当前对话"""
    try:
        from app.cache.redis_cache import redis_client
        current_key = get_current_conversation_key(user_id)
        current_conversation = redis_client.get(current_key) or []
        return current_conversation
    except Exception as e:
        print(f"获取当前对话失败: {e}")
        return []

async def clear_current_conversation(user_id: str) -> bool:
    """清空当前对话（但保留完整历史记录）"""
    try:
        from app.cache.redis_cache import redis_client
        current_key = get_current_conversation_key(user_id)
        redis_client.delete(current_key)
        return True
    except Exception as e:
        print(f"清空当前对话失败: {e}")
        return False

async def create_new_conversation(user_id: str) -> str:
    """创建新对话（清空当前对话，保留历史）"""
    try:
        await clear_current_conversation(user_id)
        return "new_conversation"
    except Exception as e:
        print(f"创建新对话失败: {e}")
        return None

def get_user_id_from_token(token: str) -> str:
    """从JWT token中提取用户ID（简化实现）"""
    try:
        from app.core.security import decode_token  # 修正函数名
        payload = decode_token(token)
        return str(payload.get("sub", "anonymous"))
    except Exception:
        return "anonymous"

async def process_uploaded_document(file_path: str, filename: str, description: str, file_extension: str, user_id: str = "anonymous") -> Dict:
    """
    处理上传的文档，解析内容并准备用于RAG
    """
    try:
        # 根据文件类型进行处理
        content = ""
        
        if file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_extension == '.pdf':
            # PDF处理（简化版，实际项目中需要安装PyPDF2或pdfplumber）
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        content += page.extract_text() + "\n"
            except ImportError:
                # 如果没有安装PDF库，返回错误
                content = f"PDF文件 '{filename}' 已接收，但服务器缺少PDF解析库。请联系管理员。"
        elif file_extension in ['.doc', '.docx']:
            # Word文档处理（简化版，实际项目中需要安装python-docx）
            try:
                import docx
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    content += para.text + "\n"
            except ImportError:
                content = f"Word文档 '{filename}' 已接收，但服务器缺少文档解析库。请联系管理员。"
        elif file_extension == '.md':
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_extension == '.csv':
            # CSV文件处理
            try:
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                content = f"CSV文件 '{filename}' 读取失败。"
        elif file_extension == '.json':
            # JSON文件处理
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 将JSON转换为易读的文本格式
                    if isinstance(data, list):
                        content = json.dumps(data, ensure_ascii=False, indent=2)
                    elif isinstance(data, dict):
                        content = json.dumps(data, ensure_ascii=False, indent=2)
                    else:
                        content = str(data)
            except Exception:
                content = f"JSON文件 '{filename}' 解析失败。"
        elif file_extension in ['.xlsx', '.xls']:
            # Excel文件处理
            try:
                import pandas as pd
                # 读取Excel文件
                if file_extension == '.xlsx':
                    df = pd.read_excel(file_path, engine='openpyxl')
                else:
                    df = pd.read_excel(file_path, engine='xlrd')
                # 将DataFrame转换为Markdown表格格式
                content = df.to_markdown(index=False)
            except ImportError:
                content = f"Excel文件 '{filename}' 已接收，但服务器缺少pandas库来解析Excel文件。"
            except Exception as e:
                content = f"Excel文件 '{filename}' 解析失败: {str(e)}"
        else:
            content = f"文件 '{filename}' 已接收，但不支持的内容解析。"
        
        # 生成文档ID
        import uuid
        document_id = str(uuid.uuid4())
        
        # 简单的文本分块（chunking）
        chunks = []
        if content:
            # 按段落分块
            paragraphs = content.split('\n')
            current_chunk = ""
            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) < 1000:  # 每块最多1000字符
                    current_chunk += paragraph + "\n"
                else:
                    if current_chunk:
                        chunks.append({"text": current_chunk.strip()})
                    current_chunk = paragraph + "\n"
            if current_chunk:
                chunks.append({"text": current_chunk.strip()})
        
        # 使用文档处理器进行向量化和存储
        success = document_processor.add_document(
            user_id=user_id,
            document_id=document_id,
            filename=filename,
            content=content,
            description=description
        )
        
        if not success:
            raise Exception("文档向量化失败")

        # 存储文件信息（实际项目中应存储到数据库）
        _uploaded_documents[document_id] = {
            "document_id": document_id,
            "user_id": user_id,  # 添加用户ID
            "filename": filename,
            "description": description,
            "file_extension": file_extension,
            "chunks": chunks,  # 存储完整的chunks信息
            "chunks_count": len(chunks),
            "total_content_length": len(content),
            "upload_time": datetime.now().isoformat(),
            "content_preview": content[:200] + "..." if len(content) > 200 else content
        }
        
        return {
            "document_id": document_id,
            "filename": filename,
            "description": description,
            "chunks_count": len(chunks),
            "total_content_length": len(content)
        }
        
    except Exception as e:
        print(f"文档处理错误: {e}")
        raise Exception(f"文档处理失败: {str(e)}")

async def get_uploaded_documents(user_id: str = "anonymous") -> List[Dict]:
    """
    获取指定用户的已上传文档列表
    """
    user_docs = []
    for doc in _uploaded_documents.values():
        if doc.get('user_id') == user_id:
            user_docs.append(doc)
    return user_docs

async def delete_uploaded_document(document_id: str) -> bool:
    """
    删除指定的上传文档
    """
    if document_id in _uploaded_documents:
        del _uploaded_documents[document_id]
        return True
    return False

def get_session_history_key(user_id: str, session_id: str) -> str:
    """获取指定会话的Redis键"""
    return f"chat_session:{user_id}:{session_id}"

def get_user_sessions_key(user_id: str) -> str:
    """获取用户所有会话列表的Redis键"""
    return f"user_sessions:{user_id}"

async def create_new_session(user_id: str) -> str:
    """创建新会话"""
    try:
        from app.cache.redis_cache import redis_client
        session_id = str(uuid.uuid4())
        
        # 初始化空消息列表
        session_key = get_session_history_key(user_id, session_id)
        redis_client.set(session_key, [], ttl=2592000)  # 30天过期
        
        # 添加到用户会话列表
        sessions_key = get_user_sessions_key(user_id)
        user_sessions = redis_client.get(sessions_key) or []
        user_sessions.insert(0, {
            "session_id": session_id,
            "title": "新对话",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
        # 只保留最近50个会话
        if len(user_sessions) > 50:
            user_sessions = user_sessions[:50]
            
        redis_client.set(sessions_key, user_sessions, ttl=2592000)
        
        return session_id
    except Exception as e:
        print(f"创建新会话失败: {e}")
        return None

async def save_message_to_session(user_id: str, session_id: str, message: dict) -> bool:
    """保存消息到指定会话"""
    try:
        from app.cache.redis_cache import redis_client
        session_key = get_session_history_key(user_id, session_id)
        
        # 获取现有消息
        messages = redis_client.get(session_key) or []
        messages.append(message)
        
        # 更新会话列表中的标题（如果是第一条用户消息）
        if len(messages) == 1 and message["role"] == "user":
            await update_session_title(user_id, session_id, message["content"])
        
        redis_client.set(session_key, messages, ttl=2592000)
        return True
    except Exception as e:
        print(f"保存消息失败: {e}")
        return False

async def update_session_title(user_id: str, session_id: str, title: str):
    """更新会话标题"""
    try:
        from app.cache.redis_cache import redis_client
        sessions_key = get_user_sessions_key(user_id)
        user_sessions = redis_client.get(sessions_key) or []
        
        for session in user_sessions:
            if session["session_id"] == session_id:
                # 截取前20个字符作为标题
                session["title"] = title[:20] + ("..." if len(title) > 20 else "")
                session["updated_at"] = datetime.now().isoformat()
                break
        
        redis_client.set(sessions_key, user_sessions, ttl=2592000)
    except Exception as e:
        print(f"更新会话标题失败: {e}")

async def get_session_messages(user_id: str, session_id: str) -> list:
    """获取指定会话的消息列表"""
    try:
        from app.cache.redis_cache import redis_client
        session_key = get_session_history_key(user_id, session_id)
        messages = redis_client.get(session_key) or []
        return messages
    except Exception as e:
        print(f"获取会话消息失败: {e}")
        return []

async def get_user_sessions(user_id: str) -> list:
    """获取用户的所有会话列表"""
    try:
        from app.cache.redis_cache import redis_client
        sessions_key = get_user_sessions_key(user_id)
        sessions = redis_client.get(sessions_key) or []
        return sessions
    except Exception as e:
        print(f"获取用户会话列表失败: {e}")
        return []

async def delete_session(user_id: str, session_id: str) -> bool:
    """删除指定会话"""
    try:
        from app.cache.redis_cache import redis_client
        session_key = get_session_history_key(user_id, session_id)
        redis_client.delete(session_key)
        
        # 从用户会话列表中移除
        sessions_key = get_user_sessions_key(user_id)
        user_sessions = redis_client.get(sessions_key) or []
        user_sessions = [s for s in user_sessions if s["session_id"] != session_id]
        redis_client.set(sessions_key, user_sessions, ttl=2592000)
        
        return True
    except Exception as e:
        print(f"删除会话失败: {e}")
        return False

async def clear_all_sessions(user_id: str) -> bool:
    """清空用户的所有会话历史"""
    try:
        from app.cache.redis_cache import redis_client
        
        # 获取用户所有会话
        sessions_key = get_user_sessions_key(user_id)
        user_sessions = redis_client.get(sessions_key) or []
        
        # 删除每个会话的消息数据
        for session in user_sessions:
            session_key = get_session_history_key(user_id, session["session_id"])
            redis_client.delete(session_key)
        
        # 清空会话列表
        redis_client.delete(sessions_key)
        
        return True
    except Exception as e:
        print(f"清空所有会话失败: {e}")
        return False