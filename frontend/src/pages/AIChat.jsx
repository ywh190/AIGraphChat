import React, { useState, useEffect, useRef } from 'react'
import { Card, Input, Button, Space, List, Avatar, message, Spin, Tag, Divider, Typography, Row, Col, Upload, Modal, Progress, Popconfirm } from 'antd'
import { SendOutlined, RobotOutlined, UserOutlined, QuestionCircleOutlined, HistoryOutlined, ClearOutlined, UploadOutlined, FileTextOutlined, FolderOpenOutlined, DeleteOutlined, LoadingOutlined, PlusOutlined } from '@ant-design/icons'
import { aiAPI } from '../services/api'
import './AIChat.css'

const { Title, Text, Paragraph } = Typography

// 简单的Markdown转HTML函数（用于基本的Markdown支持）
const renderMarkdown = (content) => {
  if (!content) return '';

  // 转义HTML特殊字符，但保留已有的HTML标签
  let html = content
    .replace(/&(?![a-zA-Z0-9#]+;)/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  // 标题
  html = html.replace(/^#{6} (.*$)/gm, '<h6>$1</h6>')
            .replace(/^#{5} (.*$)/gm, '<h5>$1</h5>')
            .replace(/^#{4} (.*$)/gm, '<h4>$1</h4>')
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>');

  // 粗体和斜体
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/___(.*?)___/g, '<strong><em>$1</em></strong>')
            .replace(/__(.*?)__/g, '<strong>$1</strong>')
            .replace(/_(.*?)_/g, '<em>$1</em>');

  // 代码块
  html = html.replace(/```(\w+)?\s*([\s\S]*?)\s*```/g, '<pre><code class="language-$1">$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');

  // 链接
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  // 特殊处理：修复AI返回的重复"1."编号问题
  // 将连续的"1. xxx"模式转换为正确的有序列表"1. xxx\n2. xxx\n3. xxx..."
  // 这种情况通常出现在AI生成的多个功能主治描述中
  
  // 先处理跨行的情况：将文本按段落分割
  const paragraphs = html.split('\n\n');
  const processedParagraphs = paragraphs.map(paragraph => {
    const lines = paragraph.split('\n');
    let oneDotCount = 0;
    
    // 统计以"1."开头的行数
    lines.forEach(line => {
      if (/^\s*1\.\s+/.test(line.trim())) {
        oneDotCount++;
      }
    });
    
    if (oneDotCount > 1) {
      // 有多个"1."开头的行，转换为正确的有序列表编号
      let counter = 1;
      return lines.map(line => {
        if (/^\s*1\.\s+/.test(line.trim())) {
          const numberedLine = line.replace(/^\s*1\.\s+/, `${counter}. `);
          counter++;
          return numberedLine;
        }
        return line;
      }).join('\n');
    }
    return paragraph;
  });
  
  html = processedParagraphs.join('\n\n');

  // 处理无序列表
  html = html.replace(/((?:^\s*-\s+.+(?:\n|$))+)/gm, (match) => {
    const items = match.trim().split('\n').filter(line => /^\s*-\s+/.test(line));
    const listItems = items.map(item => {
      const content = item.replace(/^\s*-\s*/, '');
      return `<li>${content}</li>`;
    }).join('');
    return `<ul>${listItems}</ul>`;
  });

  // 处理有序列表（正常的有序列表）
  html = html.replace(/((?:^\s*\d+\.\s+.+(?:\n|$))+)/gm, (match) => {
    const items = match.trim().split('\n').filter(line => /^\s*\d+\.\s+/.test(line));
    const listItems = items.map(item => {
      const content = item.replace(/^\s*\d+\.\s*/, '');
      return `<li>${content}</li>`;
    }).join('');
    return `<ol>${listItems}</ol>`;
  });

  // 引用
  html = html.replace(/^>\s+(.*$)/gm, '<blockquote>$1</blockquote>');

  // 分割线
  html = html.replace(/^---$/gm, '<hr>')
            .replace(/^\*\*\*$/gm, '<hr>');

  // 表格
  html = html.replace(/\|(.+)\|/g, (match, content) => {
    if (content.includes('---')) {
      // 表头分隔行
      return '<thead><tr>' + content.split('|').map(cell => `<th>${cell.trim()}</th>`).join('') + '</tr></thead>';
    } else {
      // 普通行
      return '<tr>' + content.split('|').map(cell => `<td>${cell.trim()}</td>`).join('') + '</tr>';
    }
  });

  // 段落
  html = html.replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

  // 包装段落
  if (!html.startsWith('<')) {
    html = `<p>${html}</p>`;
  }

  // 移除多余的空段落
  html = html.replace(/<p><\/p>/g, '');

  return html;
};

const AIChat = () => {
  const [messages, setMessages] = useState([]) // 当前会话的消息列表
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState([
    '什么是君臣佐使？',
    '麻黄汤的组成是什么？',
    '人参的功效有哪些？',
    '治疗感冒的中成药有哪些？',
  ])
  const [sessions, setSessions] = useState([]) // 用户的所有会话列表
  const [currentSessionId, setCurrentSessionId] = useState(null) // 当前会话ID
  const [historyVisible, setHistoryVisible] = useState(false)
  const [uploadVisible, setUploadVisible] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [filesLoading, setFilesLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false) // 防止重复加载会话列表
  const messagesEndRef = useRef(null)

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 加载用户会话列表
  useEffect(() => {
    loadUserSessions()
  }, [])

  // 加载已上传的文件
  useEffect(() => {
    loadUploadedFiles()
  }, [])

  // 加载用户会话列表
  const loadUserSessions = async () => {
    // 防止重复加载
    if (sessionsLoading) {
      return;
    }

    setSessionsLoading(true)
    try {
      const response = await aiAPI.getUserSessions()
      setSessions(response.sessions || [])

      // 如果没有当前会话，才处理
      if (!currentSessionId) {
        if ((response.sessions?.length || 0) > 0) {
          // 默认加载最新的会话
          const latestSession = response.sessions[0]
          setCurrentSessionId(latestSession.session_id)
          loadSessionMessages(latestSession.session_id)
        } else {
          // 没有会话时创建新会话
          const newSessionId = await createSessionOnly()
          if (newSessionId) {
            setCurrentSessionId(newSessionId)
            setMessages([])
          }
        }
      }
    } catch (error) {
      console.error('加载会话列表失败:', error)
      // 如果加载失败且没有当前会话，创建新会话
      if (!currentSessionId) {
        const newSessionId = await createSessionOnly()
        if (newSessionId) {
          setCurrentSessionId(newSessionId)
          setMessages([])
        }
      }
    } finally {
      setSessionsLoading(false)
    }
  }

  // 仅创建会话，不更新状态（供内部使用）
  const createSessionOnly = async () => {
    try {
      const response = await aiAPI.createNewSession()
      if (response.success) {
        return response.session_id;
      }
    } catch (error) {
      console.error('创建会话失败:', error)
    }
    return null;
  }

  // 加载指定会话的消息
  const loadSessionMessages = async (sessionId) => {
    try {
      const response = await aiAPI.getSessionMessages(sessionId)
      setMessages(response.messages || [])
      setCurrentSessionId(sessionId)
    } catch (error) {
      console.error('加载会话消息失败:', error)
      message.error('加载会话消息失败')
    }
  }

  const handleSuggestionClick = (suggestion) => {
    setInputValue(suggestion)
  }

  const handleClearCurrentSession = () => {
    // 只清空当前会话的消息，不影响历史记录
    setMessages([])
    message.success('当前对话已清空')
  }

  const handleClearAllSessions = async () => {
    try {
      await aiAPI.clearAllSessions()
      message.success('所有对话历史已清空')
      // 重新加载会话列表（应该为空）
      loadUserSessions()
      // 创建新会话
      await handleNewSession()
    } catch (error) {
      console.error('清空所有对话历史失败:', error)
      message.error('清空对话历史失败')
    }
  }

  const handleNewSession = async () => {
    try {
      const response = await aiAPI.createNewSession()
      if (response.success) {
        // 更新会话列表
        await loadUserSessions()
        // 设置为当前会话
        setCurrentSessionId(response.session_id)
        setMessages([])
        message.success('新对话已创建')
      } else {
        message.error('创建新对话失败')
      }
    } catch (error) {
      console.error('创建新会话失败:', error)
      message.error('创建新对话失败')
    }
  }

  const handleSend = async () => {
    if (!inputValue.trim()) {
      return
    }

    const userMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
      status: 'sending'
    }

    // 添加用户消息到当前消息列表
    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setLoading(true)

    // 创建AI消息，初始内容为空
    const aiMessage = {
      id: `msg_${Date.now() + 1}`,
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      status: 'streaming'
    }

    // 添加AI消息到消息列表
    setMessages(prev => [...prev, aiMessage])

    try {
      let fullContent = ''
      // 使用流式API
      for await (const chunk of aiAPI.chatStream({
        message: userMessage.content,
        session_id: currentSessionId
      })) {
        // 确保chunk是字符串类型
        const textChunk = typeof chunk === 'string' ? chunk : String(chunk)
        // 将chunk按字符拆分，实现逐字显示
        for (const char of textChunk) {
          fullContent += char
          // 更新AI消息内容，实现打字机效果
          setMessages(prev => {
            const updatedMessages = [...prev]
            const lastMessage = updatedMessages[updatedMessages.length - 1]
            if (lastMessage && lastMessage.role === 'assistant') {
              lastMessage.content = fullContent
            }
            return updatedMessages
          })
          // 添加短暂延迟，使打字效果更自然
          await new Promise(resolve => setTimeout(resolve, 10))
        }
      }

      // 流式传输完成，更新消息状态
      setMessages(prev => {
        const updatedMessages = [...prev]
        // 更新用户消息状态
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'user' && updatedMessages[i].status === 'sending') {
            updatedMessages[i].status = 'done'
            break
          }
        }
        // 更新AI消息状态
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'assistant' && updatedMessages[i].status === 'streaming') {
            updatedMessages[i].status = 'done'
            break
          }
        }
        return updatedMessages
      })

      // 更新会话列表（标题会自动更新）
      loadUserSessions()
    } catch (error) {
      message.error('发送消息失败')
      console.error(error)

      // 更新用户消息状态为error
      setMessages(prev => {
        const updatedMessages = [...prev]
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'user' && updatedMessages[i].status === 'sending') {
            updatedMessages[i].status = 'error'
            break
          }
        }
        // 更新AI消息状态为error
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'assistant' && updatedMessages[i].status === 'streaming') {
            updatedMessages[i].status = 'error'
            break
          }
        }
        return updatedMessages
      })
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteSession = async (session) => {
    try {
      // 先本地更新状态，避免UI延迟
      const isCurrentSession = currentSessionId === session.session_id;
      const remainingSessions = sessions.filter(s => s.session_id !== session.session_id);

      // 如果删除的是当前会话
      if (isCurrentSession) {
        setCurrentSessionId(null);
        setMessages([]);
      }

      // 如果删除后没有会话了，直接创建新对话
      if (remainingSessions.length === 0) {
        // 先本地更新会话列表（清空）
        setSessions([]);

        // 创建新对话
        const newSessionId = await createSessionOnly();
        if (newSessionId) {
          const newSession = {
            session_id: newSessionId,
            title: '新对话',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          };
          setSessions([newSession]);
          setCurrentSessionId(newSessionId);
          message.success('已删除旧对话并创建新对话');
        }
      } else {
        // 还有会话，更新列表
        setSessions(remainingSessions);
        await aiAPI.deleteSession(session.session_id);
        message.success('会话已删除');
      }

    } catch (error) {
      console.error('删除会话失败:', error)
      message.error('删除会话失败')
    }
  }

  const handleHistoryClick = (session) => {
    loadSessionMessages(session.session_id)
    setHistoryVisible(false)
  }

  // 文件上传处理
  const handleFileUpload = async (file) => {
    const isAllowedType = file.type === 'text/plain' ||
                         file.type === 'application/pdf' ||
                         file.type === 'application/msword' ||
                         file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
                         file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                         file.type === 'application/vnd.ms-excel' ||
                         file.name.endsWith('.md') ||
                         file.name.endsWith('.csv') ||
                         file.name.endsWith('.json') ||
                         file.name.endsWith('.xlsx') ||
                         file.name.endsWith('.xls') ||
                         file.type === 'text/csv' ||
                         file.type === 'application/json';

    if (!isAllowedType) {
      message.error('仅支持 TXT、PDF、DOC、DOCX、MD、CSV、JSON、XLSX 格式的文件！');
      return false;
    }

    if (file.size > 10 * 1024 * 1024) { // 10MB限制
      message.error('文件大小不能超过10MB！');
      return false;
    }

    return true;
  }

  const handleUpload = async (options) => {
    const { file, onSuccess, onError } = options;

    setUploading(true)
    setUploadProgress(0)
    let progressInterval = null;

    try {
      // 模拟上传进度（实际项目中可以从axios的onUploadProgress获取）
      progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + 10;
        });
      }, 200);

      const result = await aiAPI.uploadDocument(file);

      if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
      }
      setUploadProgress(100);

      message.success('文件上传成功！文档已添加到您的私人知识库。');
      onSuccess(result, file);
      setUploadVisible(false);
      // 重新加载文件列表
      loadUploadedFiles();
    } catch (error) {
      if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
      }
      console.error('文件上传失败:', error);
      message.error(`文件上传失败: ${error.response?.data?.detail || error.message || '未知错误'}`);
      onError(error);
    } finally {
      setUploading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  }

  const showUploadModal = () => {
    setUploadVisible(true);
  }

  const hideUploadModal = () => {
    setUploadVisible(false);
    setUploading(false);
    setUploadProgress(0);
  }

  // 加载已上传的文件
  const loadUploadedFiles = async () => {
    setFilesLoading(true)
    try {
      const response = await aiAPI.getUploadedDocuments()
      setUploadedFiles(response.documents || [])
    } catch (error) {
      console.error('加载文件列表失败:', error)
      message.error('加载文件列表失败')
    } finally {
      setFilesLoading(false)
    }
  }

  // 删除文件
  const handleDeleteFile = async (documentId, filename) => {
    try {
      await aiAPI.deleteUploadedDocument(documentId)
      message.success(`文件 "${filename}" 已删除`)
      loadUploadedFiles()
    } catch (error) {
      console.error('删除文件失败:', error)
      message.error('删除文件失败')
    }
  }

  return (
    <div className="ai-chat-container">
      <div className="ai-chat-header">
        <div className="header-left">
          <Title level={3} style={{ margin: 0 }}>
            <RobotOutlined style={{ marginRight: 8, color: '#1890ff' }} />
            AI智能问答
          </Title>
          <Text type="secondary" style={{ marginLeft: 16 }}>
            基于中医药材、方剂、中成药数据的智能问答系统
          </Text>
        </div>
        <div className="header-right">
          {uploadedFiles.length > 0 && (
            <Button
              icon={<FileTextOutlined />}
              onClick={() => {
                // 如果有文件，滚动到文件列表位置
                const filesSection = document.querySelector('.files-sidebar');
                if (filesSection) {
                  filesSection.scrollIntoView({ behavior: 'smooth' });
                }
              }}
            >
              文件 ({uploadedFiles.length})
            </Button>
          )}
          <Button
            icon={<FolderOpenOutlined />}
            onClick={showUploadModal}
          >
            上传文件
          </Button>
          <Button
            icon={<HistoryOutlined />}
            onClick={() => setHistoryVisible(!historyVisible)}
          >
            历史记录
          </Button>
          <Button
            icon={<PlusOutlined />}
            onClick={handleNewSession}
          >
            新建对话
          </Button>
        </div>
      </div>

      <div className="ai-chat-body">
        {/* 左侧历史记录面板 */}
        {historyVisible && (
          <div className="chat-history-panel">
            <div className="history-header">
              <Text strong>对话历史</Text>
              <Popconfirm
                title="确定要清空所有对话历史吗？此操作不可恢复！"
                onConfirm={handleClearAllSessions}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button
                  type="text"
                  size="small"
                  icon={<ClearOutlined />}
                  danger
                >
                  清除全部
                </Button>
              </Popconfirm>
            </div>
            <List
              dataSource={sessions}
              renderItem={(session) => (
                <List.Item
                  className="history-item"
                  onClick={() => handleHistoryClick(session)}
                  actions={[
                    <Popconfirm
                      key="delete"
                      title="确定要删除这个会话吗？"
                      onConfirm={(e) => {
                        // 阻止事件冒泡，避免触发onClick切换会话
                        e?.stopPropagation?.();
                        handleDeleteSession(session);
                      }}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}  // 阻止点击事件冒泡
                      />
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    avatar={<QuestionCircleOutlined style={{ fontSize: 16 }} />}
                    title={
                      <Text ellipsis style={{ width: '100%' }}>
                        {session.title || '未命名对话'}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          </div>
        )}

        {/* 主聊天区域 - 改为左右布局 */}
        <div className="chat-main">
          <div className="chat-content">
            {/* 消息列表 */}
            <div className="messages-container">
              {messages.length === 0 && (
                <div className="welcome-message">
                  <RobotOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 16 }} />
                  <Title level={2}>欢迎使用AI智能问答</Title>
                  <Text type="secondary">请输入您的中医药相关问题...</Text>
                  <Divider />
                  <Space wrap>
                    {suggestions.map((suggestion, index) => (
                      <Card
                        key={index}
                        size="small"
                        className="suggestion-card"
                        onClick={() => handleSuggestionClick(suggestion)}
                        hoverable
                      >
                        {suggestion}
                      </Card>
                    ))}
                  </Space>
                </div>
              )}

              <List
                className="messages-list"
                dataSource={messages}
                renderItem={(msg) => (
                  <div
                    className={`message-item ${msg.role === 'user' ? 'user-message' : 'ai-message'}`}
                  >
                    {/* 移除头像，只保留消息内容卡片 */}
                    <Card
                      className={`message-card ${msg.role === 'user' ? 'user-card' : 'ai-card'}`}
                    >
                      <div
                        className="message-content"
                        dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                      />
                      {/* 显示消息状态 */}
                      {msg.status === 'streaming' && (
                        <div className="message-status">
                          <Spin size="small" />
                          <Text type="secondary" style={{ marginLeft: 8 }}>AI正在输入...</Text>
                        </div>
                      )}
                      {msg.status === 'error' && (
                        <div className="message-status error">
                          <Text type="danger">发送失败</Text>
                        </div>
                      )}
                    </Card>
                  </div>
                )}
              />
              {loading && !messages.some(msg => msg.status === 'streaming') && (
                <div className="loading-message">
                  <Space>
                    <Spin />
                    <Text>AI正在思考...</Text>
                  </Space>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 - 移到聊天主区域内部 */}
            <div className="input-container">
              <div className="input-wrapper">
                <Input.TextArea
                  className="message-input"
                  placeholder="输入您的问题，按Enter发送..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  disabled={loading}
                  autoSize={{ minRows: 1, maxRows: 4 }}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  disabled={loading || !inputValue.trim()}
                  className="send-button"
                >发送
                </Button>
              </div>
            </div>
          </div>

          {/* 右侧文件列表 - 正确放置在聊天区域右侧 */}
          {uploadedFiles.length > 0 && (
            <div className="files-sidebar">
              <div className="files-sidebar-header">
                <Space>
                  <FolderOpenOutlined />
                  <Text strong>知识库 ({uploadedFiles.length})</Text>
                </Space>
              </div>
              <div className="files-list-container">
                <List
                  dataSource={uploadedFiles}
                  renderItem={(file) => (
                    <List.Item
                      actions={[
                        <Popconfirm
                          key="delete"
                          title={`确定要删除文件 "${file.filename}" 吗？`}
                          onConfirm={() => handleDeleteFile(file.document_id, file.filename)}
                          okText="确定"
                          cancelText="取消"
                        >
                          <Button type="text" icon={<DeleteOutlined />} size="small">
                            删除
                          </Button>
                        </Popconfirm>
                      ]}
                    >
                      <List.Item.Meta
                        avatar={<FileTextOutlined style={{ fontSize: 20, color: '#1890ff' }} />}
                        title={<Text>{file.filename}</Text>}
                        description={
                          <Space size="small">
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {file.file_extension?.toUpperCase()} | {file.chunks_count} 个片段
                            </Text>
                            {file.description && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {file.description}
                              </Text>
                            )}
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 文件上传模态框 */}
      <Modal
        title={
          <Space>
            <FolderOpenOutlined />
            <span>上传文档到私人知识库</span>
          </Space>
        }
        open={uploadVisible}
        onCancel={hideUploadModal}
        footer={null}
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            支持格式：TXT、PDF、DOC、DOCX、MD、CSV、JSON、XLSX、XLS 文件（最大10MB）
          </Text>
          <br />
          <Text type="secondary">
            上传的文档将被处理并添加到您的私人知识库中，AI可以基于这些文档回答相关问题。
          </Text>
        </div>

        {uploading && (
          <div style={{ marginBottom: 16 }}>
            <Progress percent={uploadProgress} status={uploadProgress === 100 ? "success" : "active"} />
          </div>
        )}

        <Upload
          customRequest={handleUpload}
          beforeUpload={handleFileUpload}
          showUploadList={false}
          disabled={uploading}
        >
          <Button
            icon={<UploadOutlined />}
            disabled={uploading}
            block
            size="large"
            style={{ height: 60 }}
          >
            {uploading ? '上传中...' : '点击选择文件或拖拽文件到这里'}
          </Button>
        </Upload>

        <div style={{ marginTop: 16, padding: 12, backgroundColor: '#f5f5f5', borderRadius: 4 }}>
          <Text strong>使用说明：</Text>
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            <li>上传的文档将用于增强AI问答能力</li>
            <li>文档内容会被自动分块和索引</li>
            <li>您可以随时上传多个文档</li>
            <li>文档仅对您个人可见</li>
          </ul>
        </div>
      </Modal>
    </div>
  )
}

export default AIChat