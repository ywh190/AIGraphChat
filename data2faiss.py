#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中医药知识图谱系统 - 数据到FAISS向量数据库转换脚本
将药材数据、中成药数据、方剂数据转换为FAISS向量数据库
使用BGE-M3嵌入模型进行文本嵌入，支持GPU加速
"""

import os
import sys
import json
import csv
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from typing import List, Dict, Tuple
import logging

# 设置环境变量避免内存碎片问题
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 直接使用用户的本地BGE-M3模型路径
MODEL_PATH = r"E:\vscode-py\model_cache\models--BAAI--bge-m3"

# 输出路径 - 使用相对于当前脚本位置的路径
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "data", "vector_db")

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_herb_data(file_path: str) -> List[Dict]:
    """加载中药材数据"""
    logger.info(f"加载中药材数据: {file_path}")
    
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        processed_data = []
        for item in data:
            name = item.get("药材名称", "")
            url = item.get("url", "")
            source_info_list = item.get("来源信息", [])
            
            if not source_info_list:
                continue
                
            source_info = source_info_list[0]  # 取第一个来源信息
            
            # 提取所有可用字段
            pinyin = source_info.get("拼音注音", "")
            aliases = source_info.get("别名", "")
            source = source_info.get("来源", "")
            habitat = source_info.get("生境分布", "")
            nature_flavor = source_info.get("性味", "")
            function_indication = source_info.get("功能主治", "")
            usage = source_info.get("用法用量", "")
            reference = source_info.get("摘录", "")
            
            # 构建完整的文本用于嵌入（包含所有重要信息）
            text_parts = [
                f"药材名称: {name}",
                f"拼音注音: {pinyin}" if pinyin else "",
                f"别名: {aliases}" if aliases else "",
                f"来源: {source}" if source else "",
                f"生境分布: {habitat}" if habitat else "",
                f"性味: {nature_flavor}" if nature_flavor else "",
                f"功能主治: {function_indication}" if function_indication else "",
                f"用法用量: {usage}" if usage else "",
                f"摘录: {reference}" if reference else ""
            ]
            text = "\n".join([part for part in text_parts if part])
            
            if text.strip():
                processed_data.append({
                    "text": text.strip(),
                    "metadata": {
                        "type": "herb",
                        "name": name,
                        "source": source or reference or "数据来源未明确",
                        "source_link": url
                    }
                })
        
        logger.info(f"成功加载 {len(processed_data)} 条药材数据")
        return processed_data
        
    except Exception as e:
        logger.error(f"加载药材数据失败: {e}")
        return []

def load_medic_data(file_path: str) -> List[Dict]:
    """加载中成药数据"""
    logger.info(f"加载中成药数据: {file_path}")
    
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return []
    
    processed_data = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        for row in csv_reader:
            # 提取所有关键字段（充分利用CSV中的所有列）
            category = row.get("科室类别", "")
            major_category = row.get("大类", "")
            minor_category = row.get("小类", "")
            name = row.get("中文名称", "")
            english_name = row.get("英文名称", "")
            composition = row.get("药物组成", "")
            function_indication = row.get("功能与主治", "")
            formula_explanation = row.get("方解", "")  # 方解
            clinical_application = row.get("临床应用", "")  # 临床应用
            adverse_reactions = row.get("不良反应", "")  # 不良反应
            contraindications = row.get("禁忌", "")  # 禁忌
            precautions = row.get("注意事项", "")  # 注意事项
            dosage = row.get("用法与用量", "")  # 用法用量
            specifications = row.get("规格", "")  # 规格
            pharmacology_toxicology = row.get("药理毒理", "")  # 药理毒理
            references = row.get("参考文献", "")  # 参考文献
            jun_chen_zuo_shi = row.get("君臣佐使", "")  # 君臣佐使
            data_source = row.get("数据来源", "《中国药典》")  # 数据来源
            
            # 构建完整的文本用于嵌入（包含所有重要信息）
            text_parts = [
                f"中成药名称: {name}",
                f"英文名称: {english_name}" if english_name else "",
                f"科室类别: {category}" if category else "",
                f"大类: {major_category}" if major_category else "",
                f"小类: {minor_category}" if minor_category else "",
                f"药物组成: {composition}" if composition else "",
                f"功能与主治: {function_indication}" if function_indication else "",
                f"方解: {formula_explanation}" if formula_explanation else "",
                f"临床应用: {clinical_application}" if clinical_application else "",
                f"不良反应: {adverse_reactions}" if adverse_reactions else "",
                f"禁忌: {contraindications}" if contraindications else "",
                f"注意事项: {precautions}" if precautions else "",
                f"用法用量: {dosage}" if dosage else "",
                f"规格: {specifications}" if specifications else "",
                f"药理毒理: {pharmacology_toxicology}" if pharmacology_toxicology else "",
                f"参考文献: {references}" if references else "",
                f"君臣佐使: {jun_chen_zuo_shi}" if jun_chen_zuo_shi else ""
            ]
            text = "\n".join([part for part in text_parts if part])
            
            if text.strip():
                processed_data.append({
                    "text": text.strip(),
                    "metadata": {
                        "type": "medic",
                        "name": name,
                        "source": data_source,  # 使用权威数据来源
                        "source_file": "中成药数据_含君臣佐使.csv"
                    }
                })
    
    logger.info(f"成功加载 {len(processed_data)} 条中成药数据")
    return processed_data

def load_prescription_data(file_path: str) -> List[Dict]:
    """加载中药方剂数据"""
    logger.info(f"加载中药方剂数据: {file_path}")
    
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        processed_data = []
        for item in data:
            name = item.get("name", "")
            prescription = item.get("prescription", "")
            function = item.get("function", "")
            usage = item.get("usage", "")
            source = item.get("source", "")
            
            # 构建完整的文本用于嵌入
            text_parts = [
                f"方剂名称: {name}",
                f"处方组成: {prescription}" if prescription else "",
                f"功效主治: {function}" if function else "",
                f"用法用量: {usage}" if usage else "",
                f"来源: {source}" if source else ""
            ]
            text = "\n".join([part for part in text_parts if part])
            
            if text.strip():
                processed_data.append({
                    "text": text.strip(),
                    "metadata": {
                        "type": "prescription",
                        "name": name,
                        "source": source or "数据来源未明确",
                        "source_file": "中药方剂数据.json"
                    }
                })
        
        logger.info(f"成功加载 {len(processed_data)} 条方剂数据")
        return processed_data
        
    except Exception as e:
        logger.error(f"加载方剂数据失败: {e}")
        return []

def create_embeddings(texts: List[str], model, batch_size: int = 32) -> np.ndarray:
    """生成文本嵌入向量"""
    logger.info(f"开始生成嵌入，共 {len(texts)} 个文本")
    
    # 清理GPU内存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # 尝试使用GPU，如果失败则降级到CPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"尝试使用设备: {device}")
    
    try:
        # 将模型移动到设备
        model.to(device)
        
        # 生成嵌入 - 使用半精度（仅在CUDA支持时）
        embeddings = model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=True,
            device=device,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
    except torch.cuda.OutOfMemoryError as e:
        logger.warning(f"CUDA内存不足，降级到CPU模式: {e}")
        # 清理GPU内存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        # 降级到CPU
        device = 'cpu'
        logger.info(f"使用设备: {device}")
        model.to(device)
        
        # 对于大文本集，使用非常小的batch_size
        if len(texts) > 10000:
            cpu_batch_size = 1  # 超大文本集使用batch_size=1
        elif len(texts) > 5000:
            cpu_batch_size = 2  # 大文本集使用batch_size=2
        else:
            cpu_batch_size = min(batch_size, 4)  # 中小文本集使用batch_size=4
        
        logger.info(f"CPU模式下使用batch_size: {cpu_batch_size}")
        
        try:
            embeddings = model.encode(
                texts, 
                batch_size=cpu_batch_size, 
                show_progress_bar=True,
                device=device,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
        except RuntimeError as cpu_error:
            if "not enough memory" in str(cpu_error):
                logger.warning(f"CPU内存不足，进一步降低batch_size到1: {cpu_error}")
                # 最后一次尝试，使用batch_size=1
                embeddings = model.encode(
                    texts, 
                    batch_size=1, 
                    show_progress_bar=True,
                    device=device,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
            else:
                raise cpu_error
    
    except Exception as e:
        logger.error(f"生成嵌入时发生错误: {e}")
        raise
    
    logger.info(f"嵌入生成完成，形状: {embeddings.shape}")
    return embeddings

def create_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """创建FAISS索引（内积相似度）"""
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # 内积相似度（余弦相似度）
    
    # 归一化嵌入向量以支持内积=余弦相似度
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    
    logger.info(f"FAISS索引创建完成，包含 {index.ntotal} 个向量")
    return index

def save_faiss_index(index: faiss.Index, texts: List[str], metadatas: List[Dict], 
                    index_path: str, metadata_path: str):
    """保存FAISS索引和元数据"""
    # 创建目录
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    
    # 保存FAISS索引
    faiss.write_index(index, index_path)
    logger.info(f"FAISS索引已保存到: {index_path}")
    
    # 保存元数据
    metadata_dict = {
        'texts': texts,
        'metadatas': metadatas
    }
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata_dict, f, ensure_ascii=False, indent=2)
    logger.info(f"元数据已保存到: {metadata_path}")

def main():
    """主函数"""
    logger.info("开始中医药知识库向量化处理...")
    
    # 加载所有数据
    all_documents = []
    
    # 数据文件路径 - 使用相对于当前脚本的路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    herb_file = os.path.join(current_dir, "药材数据.json")
    patent_medicine_file = os.path.join(current_dir, "中成药数据_含君臣佐使.csv")
    prescription_file = os.path.join(current_dir, "中药方剂数据.json")
    
    # 药材数据
    if os.path.exists(herb_file):
        all_documents.extend(load_herb_data(herb_file))
    else:
        logger.warning(f"药材数据文件未找到: {herb_file}")
    
    # 中成药数据
    if os.path.exists(patent_medicine_file):
        all_documents.extend(load_medic_data(patent_medicine_file))
    else:
        logger.warning(f"中成药数据文件未找到: {patent_medicine_file}")
    
    # 方剂数据
    if os.path.exists(prescription_file):
        all_documents.extend(load_prescription_data(prescription_file))
    else:
        logger.warning(f"方剂数据文件未找到: {prescription_file}")
    
    if not all_documents:
        logger.error("未找到任何有效数据，请检查数据文件路径")
        return
    
    logger.info(f"总共加载了 {len(all_documents)} 条文档")
    
    # 提取文本和元数据
    texts = [doc["text"] for doc in all_documents]
    metadatas = [doc["metadata"] for doc in all_documents]
    
    # 加载BGE-M3模型
    model_path = MODEL_PATH
    logger.info(f"加载BGE-M3模型: {model_path}")
    
    # 检查模型路径是否存在
    if not os.path.exists(model_path):
        logger.error(f"模型路径不存在: {model_path}")
        logger.error("请确保BGE-M3模型已下载到指定路径")
        return
    
    # 先使用CPU加载模型，避免torch.load安全问题
    logger.info("使用CPU加载模型...")
    model = SentenceTransformer(model_path, device='cpu')
    
    # 生成嵌入向量（强制使用CPU，避免内存问题）
    logger.info("开始生成嵌入向量...")
    # 对于超大文本集（>30000），使用非常保守的batch_size
    if len(texts) > 30000:
        initial_batch_size = 1
    elif len(texts) > 10000:
        initial_batch_size = 2
    else:
        initial_batch_size = 4
        
    embeddings = create_embeddings(texts, model, batch_size=initial_batch_size)
    
    # 创建FAISS索引
    index = create_faiss_index(embeddings)
    
    # 保存结果到backend目录
    index_path = os.path.join(OUTPUT_DIR, "knowledge_base.index")
    metadata_path = os.path.join(OUTPUT_DIR, "knowledge_base_metadata.json")
    save_faiss_index(index, texts, metadatas, index_path, metadata_path)
    
    logger.info("中医药知识库向量化处理完成！")
    logger.info(f"向量数据库保存位置: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()