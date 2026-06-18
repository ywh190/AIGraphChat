from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.session import get_db
from app.models import schemas
from app.services import ai_service
from typing import Optional
import os
import tempfile
import shutil
import json

router = APIRouter()

@router.post("/chat")
async def chat_with_ai(chat_request: schemas.ChatRequest, db: Session = Depends(get_db), authorization: Optional[str] = Header(None)):
    """与AI对话，基于RAG的智能问答"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        # 如果没有提供session_id，创建新会话
        session_id = chat_request.session_id
        if not session_id:
            session_id = await ai_service.create_new_session(user_id)
            if not session_id:
                raise HTTPException(status_code=500, detail="创建会话失败")
        
        # 获取当前会话的完整消息历史（用于上下文）
        conversation_history = await ai_service.get_session_messages(user_id, session_id)
        
        # 获取问题文本
        question = chat_request.message
        response = await ai_service.chat_with_context(question, None, db, conversation_history, user_id)
        
        # 保存用户消息
        user_message = {
            "id": f"msg_{int(datetime.now().timestamp() * 1000)}",
            "role": "user",
            "content": question,
            "timestamp": datetime.now().isoformat(),
            "status": "done"
        }
        await ai_service.save_message_to_session(user_id, session_id, user_message)
        
        # 保存AI回复
        ai_message = {
            "id": f"msg_{int(datetime.now().timestamp() * 1000) + 1}",
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
            "status": "done"
        }
        await ai_service.save_message_to_session(user_id, session_id, ai_message)
        
        return {"response": response, "session_id": session_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

@router.post("/chat/stream")
async def chat_with_ai_stream(chat_request: schemas.ChatRequest, db: Session = Depends(get_db), authorization: Optional[str] = Header(None)):
    """与AI对话，基于RAG的智能问答（流式返回）"""
    async def generate_stream():
        try:
            user_id = "anonymous"
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]
                user_id = ai_service.get_user_id_from_token(token)

            # 如果没有提供session_id，创建新会话
            session_id = chat_request.session_id
            if not session_id:
                session_id = await ai_service.create_new_session(user_id)
                if not session_id:
                    yield f"data: {json.dumps({'error': '创建会话失败'})}\n\n"
                    return

            # 获取当前会话的完整消息历史（用于上下文）
            conversation_history = await ai_service.get_session_messages(user_id, session_id)

            # 获取问题文本
            question = chat_request.message

            # 保存用户消息
            user_message = {
                "id": f"msg_{int(datetime.now().timestamp() * 1000)}",
                "role": "user",
                "content": question,
                "timestamp": datetime.now().isoformat(),
                "status": "done"
            }
            await ai_service.save_message_to_session(user_id, session_id, user_message)

            # 使用流式AI服务获取响应
            full_response = ""
            async for chunk in ai_service.chat_with_context_stream(question, None, db, conversation_history, user_id):
                full_response += chunk
                # 使用SSE格式发送数据
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            # 保存完整的AI回复
            ai_message = {
                "id": f"msg_{int(datetime.now().timestamp() * 1000) + 1}",
                "role": "assistant",
                "content": full_response,
                "timestamp": datetime.now().isoformat(),
                "status": "done"
            }
            await ai_service.save_message_to_session(user_id, session_id, ai_message)

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'AI service error: {str(e)}'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/new-session")
async def create_new_session(authorization: Optional[str] = Header(None)):
    """创建新会话"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        session_id = await ai_service.create_new_session(user_id)
        if session_id:
            return {"success": True, "session_id": session_id, "message": "新会话已创建"}
        else:
            raise HTTPException(status_code=500, detail="创建新会话失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建新会话失败: {str(e)}")

@router.get("/sessions")
async def get_user_sessions(authorization: Optional[str] = Header(None)):
    """获取用户的所有会话列表"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        sessions = await ai_service.get_user_sessions(user_id)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@router.delete("/sessions")
async def clear_all_sessions(authorization: Optional[str] = Header(None)):
    """清空用户的所有会话历史"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        success = await ai_service.clear_all_sessions(user_id)
        if success:
            return {"success": True, "message": "所有对话历史已清空"}
        else:
            raise HTTPException(status_code=500, detail="清空对话历史失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空对话历史失败: {str(e)}")

@router.get("/session/{session_id}")
async def get_session_messages(session_id: str, authorization: Optional[str] = Header(None)):
    """获取指定会话的消息列表"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        messages = await ai_service.get_session_messages(user_id, session_id)
        return {"messages": messages, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话消息失败: {str(e)}")

@router.delete("/session/{session_id}")
async def delete_session(session_id: str, authorization: Optional[str] = Header(None)):
    """删除指定的会话（保留其他会话历史）"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        success = await ai_service.delete_session(user_id, session_id)
        if success:
            return {"success": True, "message": "会话删除成功"}
        else:
            raise HTTPException(status_code=404, detail="会话未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

@router.get("/conversation-history")
async def get_conversation_history(authorization: Optional[str] = Header(None), limit: int = 20):
    """获取完整对话历史"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        history = await ai_service.get_conversation_history(user_id, limit)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")

@router.delete("/conversation-history")
async def clear_conversation_history(authorization: Optional[str] = Header(None)):
    """清空对话历史"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        success = await ai_service.clear_conversation_history(user_id)
        if success:
            return {"success": True, "message": "对话历史已清空"}
        else:
            raise HTTPException(status_code=500, detail="清空对话历史失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空对话历史失败: {str(e)}")

@router.get("/current-conversation")
async def get_current_conversation(authorization: Optional[str] = Header(None)):
    """获取当前对话"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        current_conversation = await ai_service.get_current_conversation(user_id)
        return {"conversation": current_conversation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取当前对话失败: {str(e)}")

@router.post("/new-conversation")
async def create_new_conversation(authorization: Optional[str] = Header(None)):
    """创建新对话（清空当前对话，保留历史记录）"""
    try:
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        result = await ai_service.create_new_conversation(user_id)
        if result:
            return {"success": True, "message": "新对话已创建", "session_id": result}
        else:
            raise HTTPException(status_code=500, detail="创建新对话失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建新对话失败: {str(e)}")

@router.post("/generate-explanation")
async def generate_explanation(request: schemas.GenerateExplanationRequest, db: Session = Depends(get_db)):
    """生成方剂或药材的详细解释"""
    try:
        explanation = await ai_service.generate_explanation(request.content_type, request.content, db)
        return {"explanation": explanation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation generation error: {str(e)}")

@router.post("/recommend-prescriptions")
async def recommend_prescriptions(request: schemas.RecommendPrescriptionsRequest, db: Session = Depends(get_db)):
    """根据症状推荐方剂"""
    try:
        recommendations = await ai_service.recommend_prescriptions(request.symptoms, db)
        return {"recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")

@router.post("/analyze-composition")
async def analyze_composition(request: schemas.AnalyzeCompositionRequest, db: Session = Depends(get_db)):
    """分析方剂组成和功效"""
    try:
        analysis = await ai_service.analyze_composition(request.composition, db)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@router.get("/embedding/{text}")
async def get_embedding(text: str):
    """获取文本的向量表示"""
    try:
        embedding = await ai_service.get_embedding(text)
        return {"embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding error: {str(e)}")

@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    description: str = Form(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    上传文档到私人知识库
    支持PDF、TXT、DOC、DOCX等格式
    """
    try:
        # 获取用户ID
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        # 验证文件类型
        allowed_extensions = {'.pdf', '.txt', '.doc', '.docx', '.md', '.csv', '.json', '.xlsx', '.xls'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式。支持的格式: {', '.join(allowed_extensions)}"
            )
        
        # 创建临时目录保存上传的文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            # 读取上传的文件内容
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # 调用AI服务处理文档（传递user_id）
        result = await ai_service.process_uploaded_document(
            temp_file_path, 
            file.filename, 
            description or "",
            file_extension,
            user_id
        )
        
        # 清理临时文件
        os.unlink(temp_file_path)
        
        return {
            "success": True,
            "message": "文档上传成功",
            "document_id": result.get("document_id"),
            "filename": file.filename,
            "file_size": len(content),
            "processed_chunks": result.get("chunks_count", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传处理失败: {str(e)}")

@router.get("/uploaded-documents")
async def get_uploaded_documents(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """
    获取当前用户的已上传文档列表
    """
    try:
        # 获取用户ID
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = ai_service.get_user_id_from_token(token)
        
        documents = await ai_service.get_uploaded_documents(user_id)
        return {"success": True, "documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取上传文档列表失败: {str(e)}")

@router.delete("/uploaded-documents/{document_id}")
async def delete_uploaded_document(document_id: str, db: Session = Depends(get_db)):
    """
    删除指定的上传文档
    """
    try:
        success = await ai_service.delete_uploaded_document(document_id)
        if success:
            return {"success": True, "message": "文档删除成功"}
        else:
            raise HTTPException(status_code=404, detail="文档未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")