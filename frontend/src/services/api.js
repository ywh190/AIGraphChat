import axios from 'axios'

const API_BASE_URL = 'http://localhost:10000/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,  // 增加超时时间到60秒
})

// 请求拦截器 - 添加认证token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
      console.log('API请求添加认证token:', config.url)
    } else {
      console.log('API请求未找到token:', config.url)
    }
    return config
  },
  (error) => {
    console.error('请求拦截器错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理401未授权错误
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 只对401未授权错误跳转到登录页面
    if (error.response && error.response.status === 401) {
      console.error('='.repeat(50))
      console.error('API未授权错误（401）:')
      console.error('请求URL:', error.config?.url)
      console.error('请求方法:', error.config?.method)
      console.error('错误详情:', error.response?.data?.detail || '未知错误')
      console.error('='.repeat(50))
      
      // 临时：显示错误消息但不自动跳转，以便调试
      alert(`未授权错误（401）\n请求: ${error.config?.method} ${error.config?.url}\n请查看控制台获取详细信息`)
      
      // 清除本地存储的认证信息
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      delete api.defaults.headers.common['Authorization']
      
      // 【临时禁用自动跳转】只有当不是登录页面时才跳转
      // if (!window.location.pathname.includes('/login')) {
      //   console.warn('登录已过期，正在跳转到登录页面...')
      //   window.location.href = '/login'
      // }
    } else if (error.response) {
      // 其他错误只打印日志，不跳转
      console.error('API错误:', error.response.status, error.response?.data?.detail || '操作失败')
    } else {
      console.error('API请求错误:', error.message)
    }
    
    return Promise.reject(error)
  }
)

// 登录函数
export const login = async (username, password) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/auth/login`, {
      username,
      password
    })
    
    // 保存token和用户信息
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
      
      // 更新默认header
      api.defaults.headers.common['Authorization'] = `Bearer ${response.data.access_token}`
    }
    
    return response.data
  } catch (error) {
    throw error
  }
}

// 登出函数
export const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  delete api.defaults.headers.common['Authorization']
  window.location.href = '/login'
}

// 获取当前用户信息
export const getCurrentUser = () => {
  const userStr = localStorage.getItem('user')
  return userStr ? JSON.parse(userStr) : null
}

// 检查用户是否为管理员
export const isAdmin = () => {
  try {
    // 开发测试模式：如果启用，可以绕过权限检查
    const devMode = localStorage.getItem('dev_mode') === 'true'
    if (devMode) {
      console.log('开发模式：允许访问管理员功能')
      return true
    }
    
    const userStr = localStorage.getItem('user')
    if (!userStr) {
      return false
    }
    
    const user = JSON.parse(userStr)
    
    // 详细记录用户信息用于调试
    console.log('isAdmin检查 - 用户信息:', user)
    console.log('isAdmin检查 - role类型:', typeof user.role, 'role值:', user.role)
    
    // 直接检查字符串类型的角色值
    if (user.role === 'admin' || user.role === 'ADMIN') {
      console.log('isAdmin检查 - 结果: 是管理员')
      return true
    }
    
    // 如果role是对象形式 (如 {"value": "admin"})
    if (user.role && typeof user.role === 'object' && user.role.value) {
      const result = user.role.value === 'admin' || user.role.value === 'ADMIN'
      console.log('isAdmin检查 - 角色对象形式, 结果:', result)
      return result
    }
    
    console.log('isAdmin检查 - 结果: 不是管理员')
    return false
  } catch (error) {
    console.error('isAdmin检查出错:', error)
    return false
  }
}

// 启用开发模式（用于测试）
export const enableDevMode = () => {
  localStorage.setItem('dev_mode', 'true')
  console.log('开发模式已启用')
}

// 禁用开发模式
export const disableDevMode = () => {
  localStorage.removeItem('dev_mode')
  console.log('开发模式已禁用')
}

// 方剂API
export const prescriptionAPI = {
  // 获取方剂列表
  getPrescriptions: (params = {}) =>
    api.get('/prescriptions/', { params }),

  // 获取方剂详情
  getPrescription: (id) =>
    api.get(`/prescriptions/${id}`),

  // 创建方剂
  createPrescription: (data) =>
    api.post('/prescriptions/', data),

  // 更新方剂
  updatePrescription: (id, data) =>
    api.put(`/prescriptions/${id}`, data),

  // 删除方剂
  deletePrescription: (id) =>
    api.delete(`/prescriptions/${id}`),

  // 搜索方剂（POST请求，支持分页和搜索类型）
  searchPrescriptions: (keyword, searchType = 'all', skip = 0, limit = 10) =>
    api.post('/prescriptions/search', { keyword, search_type: searchType, skip, limit }),

  // 按分类获取（新模型中已移除category字段，此端点返回空数组以兼容旧API）
  getByCategory: (category, subCategory, params = {}) =>
    api.get(`/prescriptions/category/${category}/subcategory/${subCategory}`, { params }),

  // 批量导入
  bulkImport: (items) =>
    api.post('/admin/prescriptions/bulk-import', items),

  // 导出所有数据
  exportAll: (format = 'csv') =>
    api.get(`/admin/export/prescriptions`, {
      params: { format },
      responseType: 'blob'
    }),

  // 获取统计数据
  getStatistics: () =>
    api.get('/prescriptions/statistics'),
}

// 药材API
export const herbAPI = {
  // 获取药材列表
  getHerbs: (params = {}) =>
    api.get('/herbs/', { params }),

  // 获取药材详情
  getHerb: (id) =>
    api.get(`/herbs/${id}`),

  // 创建药材
  createHerb: (data) =>
    api.post('/herbs/', data),

  // 更新药材
  updateHerb: (id, data) =>
    api.put(`/herbs/${id}`, data),

  // 删除药材
  deleteHerb: (id) =>
    api.delete(`/herbs/${id}`),

  // 搜索药材（POST请求，支持按性味筛选、搜索类型和分页）
  searchHerbs: (keyword, nature, searchType = 'all', skip = 0, limit = 10) =>
    api.post('/herbs/search', { keyword, nature, search_type: searchType, skip, limit }),

  // 按名称获取
  getByName: (name) =>
    api.get(`/herbs/name/${name}`),

  // 按分类获取
  getByCategory: (category, params = {}) =>
    api.get(`/herbs/category/${category}`, { params }),

  // 批量导入
  bulkImport: (items) =>
    api.post('/admin/herbs/bulk-import', items),

  // 导出所有数据
  exportAll: (format = 'csv') =>
    api.get(`/admin/export/herbs`, {
      params: { format },
      responseType: 'blob'
    }),

  // 获取统计数据
  getStatistics: () =>
    api.get('/herbs/statistics'),
}

// 中成药API
export const medicAPI = {
  // 获取中成药列表
  getMedics: (params = {}) =>
    api.get('/medics/', { params }),

  // 获取中成药详情
  getMedic: (id) =>
    api.get(`/medics/${id}`),

  // 创建中成药
  createMedic: (data) =>
    api.post('/medics/', data),

  // 更新中成药
  updateMedic: (id, data) =>
    api.put(`/medics/${id}`, data),

  // 删除中成药
  deleteMedic: (id) =>
    api.delete(`/medics/${id}`),

  // 搜索中成药（支持搜索类型）
  searchMedics: (params) => {
    // 如果params是字符串，转换为对象
    if (typeof params === 'string') {
      return api.post('/medics/search', { keyword: params, search_type: 'all', skip: 0, limit: 10 })
    }
    // 确保search_type被正确传递
    return api.post('/medics/search', params)
  },

  // 按名称获取
  getByName: (name) =>
    api.get(`/medics/name/${name}`),

  // 按科室类别获取
  getByCategory: (category, params = {}) =>
    api.get(`/medics/category/${category}`, { params }),

  // 按大类获取
  getByMainCategory: (mainCategory, params = {}) =>
    api.get(`/medics/main-category/${mainCategory}`, { params }),

  // 按小类获取
  getBySubCategory: (subCategory, params = {}) =>
    api.get(`/medics/sub-category/${subCategory}`, { params }),

  // 批量导入
  bulkImport: (items) =>
    api.post('/admin/medics/bulk-import', items),

  // 导出所有数据
  exportAll: (format = 'csv') =>
    api.get(`/admin/export/medics`, {
      params: { format },
      responseType: 'blob'
    }),

  // 获取统计数据
  getStatistics: () =>
    api.get('/medics/statistics'),
}

// 搜索API
export const searchAPI = {
  // 搜索方剂
  searchPrescriptions: (query, limit = 10) =>
    api.get(`/search/prescriptions/${query}`, { params: { limit } }),

  // 搜索药材
  searchHerbs: (query, limit = 10) =>
    api.get(`/search/herbs/${query}`, { params: { limit } }),

  // 语义搜索
  semanticSearch: (query) =>
    api.post('/search/semantic', query),

  // 高级搜索
  advancedSearch: (query) =>
    api.get(`/search/advanced/${query}`),
}

// AI API
export const aiAPI = {
  // AI聊天
  chat: (data) =>
    api.post('/ai/chat', data),

  // AI流式聊天
  chatStream: async function*(data) {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_BASE_URL}/ai/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        // 处理SSE格式的数据
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              return;
            }
            try {
              const json = JSON.parse(data);
              // 确保返回的是字符串内容
              if (json.content !== undefined) {
                yield json.content;
              } else if (json.error) {
                throw new Error(json.error);
              } else {
                // 如果没有content字段，返回整个json的字符串形式
                yield JSON.stringify(json);
              }
            } catch (e) {
              // 如果不是JSON格式，直接返回文本
              if (data) {
                yield data;
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  // 创建新会话
  createNewSession: () =>
    api.post('/ai/new-session'),

  // 获取用户所有会话列表
  getUserSessions: () =>
    api.get('/ai/sessions'),

  // 获取指定会话的消息
  getSessionMessages: (sessionId) =>
    api.get(`/ai/session/${sessionId}`),

  // 删除指定会话
  deleteSession: (sessionId) =>
    api.delete(`/ai/session/${sessionId}`),

  // 清空所有会话历史
  clearAllSessions: () =>
    api.delete('/ai/sessions'),

  // 生成解释
  generateExplanation: (data) =>
    api.post('/ai/generate-explanation', data),

  // 推荐方剂
  recommendPrescriptions: (symptoms) =>
    api.post('/ai/recommend-prescriptions', { symptoms }),

  // 分析组成
  analyzeComposition: (composition) =>
    api.post('/ai/analyze-composition', { composition }),

  // 获取嵌入向量
  getEmbedding: (text) =>
    api.get(`/ai/embedding/${text}`),

  // 上传文档到私人知识库
  uploadDocument: async (file, description = '') => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) {
      formData.append('description', description);
    }
    
    try {
      const response = await axios.post(`${API_BASE_URL}/ai/upload-document`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': localStorage.getItem('token') ? `Bearer ${localStorage.getItem('token')}` : ''
        },
        timeout: 300000 // 5分钟超时，文档处理需要解析、分块、生成嵌入向量
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // 获取已上传的文档列表
  getUploadedDocuments: () =>
    api.get('/ai/uploaded-documents'),

  // 删除上传的文档
  deleteUploadedDocument: (documentId) =>
    api.delete(`/ai/uploaded-documents/${documentId}`)
}

// 知识图谱API
export const knowledgeGraphAPI = {
  // 获取药材关系
  getHerbRelationships: (herbName, depth = 2, limit = 30, skip = 0, relationshipTypes = null) =>
    api.get(`/knowledge-graph/herb-relationships/${herbName}`, {
      params: { 
        depth,
        limit,
        skip,
        relationship_types: relationshipTypes
      }
    }),

  // 获取方剂关系
  getPrescriptionRelationships: (prescriptionName, depth = 2, limit = 30, skip = 0, relationshipTypes = null) =>
    api.get(`/knowledge-graph/prescription-relationships/${prescriptionName}`, {
      params: { 
        depth,
        limit,
        skip,
        relationship_types: relationshipTypes
      }
    }),

  // 获取中成药关系
  getMedicRelationships: (medicName, depth = 2, limit = 30, skip = 0, relationshipTypes = null) =>
    api.get(`/knowledge-graph/medic-relationships/${medicName}`, {
      params: { 
        depth,
        limit,
        skip,
        relationship_types: relationshipTypes
      }
    }),

  // 获取中成药详细信息（包含君臣佐使）
  getMedicDetails: (medicName, includeHerbs = true, includeDetails = true) =>
    api.get(`/knowledge-graph/medic/${medicName}`, {
      params: { 
        include_herbs: includeHerbs,
        include_details: includeDetails
      }
    }),

  // 获取中成药知识图谱（包含君臣佐使分组）
  getMedicGraph: (medicName, depth = 2, limit = 100) =>
    api.get(`/knowledge-graph/medic/${medicName}/graph`, {
      params: { depth, limit }
    }),

  // 查找路径
  findPathBetween: (source, target, maxDepth = 3) =>
    api.get(`/knowledge-graph/path-between/${source}/${target}`, {
      params: { maxDepth }
    }),

  // 查找相似药材
  findSimilarHerbs: (herbName, limit = 5) =>
    api.get(`/knowledge-graph/similar-herbs/${herbName}`, {
      params: { limit }
    }),

  // 查找相似方剂
  findSimilarPrescriptions: (prescriptionName, limit = 5) =>
    api.get(`/knowledge-graph/similar-prescriptions/${prescriptionName}`, {
      params: { limit }
    }),

  // 查找相似中成药
  findSimilarMedics: (medicName, limit = 5) =>
    api.get(`/knowledge-graph/similar-medics/${medicName}`, {
      params: { limit }
    }),

  // 获取药材-功效网络
  getHerbEfficacyNetwork: (herbName) =>
    api.get(`/knowledge-graph/herb-efficacy-network/${herbName}`),

  // 获取包含某药材的所有中成药
  getHerbMedics: (herbName) =>
    api.get(`/knowledge-graph/herb-medics/${herbName}`),

  // 获取包含某药材的所有方剂
  getHerbPrescriptions: (herbName) =>
    api.get(`/knowledge-graph/herb-prescriptions/${herbName}`),

  // 执行Cypher查询
  executeCypherQuery: (query) =>
    api.post('/knowledge-graph/query', { query }),

  // =========== 新增增强功能 ===========
  
  // 获取图谱统计
  getGraphStatistics: () =>
    api.get('/knowledge-graph/graph-statistics'),

  // 按标签获取节点统计
  getNodeStatistics: (label) =>
    api.get(`/knowledge-graph/node-statistics/${label}`),

  // 查找所有路径
  findAllPathsBetween: (source, target, maxDepth = 3, limit = 10) =>
    api.get(`/knowledge-graph/all-paths-between/${source}/${target}`, {
      params: { maxDepth, limit }
    }),

  // 查找带权最短路径
  findShortestWeightedPath: (source, target, weightProperty = "weight") =>
    api.get(`/knowledge-graph/shortest-weighted-path/${source}/${target}`, {
      params: { weightProperty }
    }),

  // 社区检测
  findCommunities: (label, maxIterations = 10) =>
    api.get(`/knowledge-graph/communities/${label}`, {
      params: { maxIterations },
      timeout: 30000  // 30秒超时，社区检测计算复杂
    }),

  // 计算中心性指标
  calculateCentrality: (label, centralityType = "degree") =>
    api.get(`/knowledge-graph/centrality/${label}/${centralityType}`, {
      timeout: 30000  // 30秒超时，中心性分析计算复杂
    }),

  // 模式匹配
  findPatternMatches: (pattern, limit = 20) =>
    api.post('/knowledge-graph/pattern-matches', { pattern, limit }),

  // 获取子图
  getSubgraph: (nodeIds, depth = 2) =>
    api.post('/knowledge-graph/subgraph', { node_ids: nodeIds, depth }),

  // 关系统计
  getRelationshipStatistics: () =>
    api.get('/knowledge-graph/relationship-statistics'),

  // 按属性搜索节点
  searchNodesByProperty: (label, propertyName, propertyValue, limit = 20) =>
    api.get(`/knowledge-graph/search-nodes/${label}`, {
      params: { property_name: propertyName, property_value: propertyValue, limit }
    }),

  // 获取节点详细信息
  getNodeDetails: (nodeName, nodeType) =>
    api.get(`/knowledge-graph/node-details/${encodeURIComponent(nodeName)}/${nodeType}`),

  // 调试接口：查看数据库信息
  debugDatabaseInfo: () =>
    api.get('/knowledge-graph/debug/database-info'),
}

// 数据同步API（仅管理员可用）
export const syncAPI = {
  // 触发全量同步
  fullSync: (params = {}) =>
    api.post('/sync', {
      direction: 'mysql_to_neo4j',
      sync_prescriptions: true,
      sync_herbs: true,
      sync_medics: true,
      sync_relationships: true,
      sync_attributes: true,
      incremental: false,
      batch_size: 1000,
      ...params
    }),

  // 触发增量同步（同步执行）
  incrementalSync: (params = {}) =>
    api.post('/sync/incremental', params),

  // 后台增量同步（异步执行，支持进度显示）
  backgroundIncrementalSync: (params = {}) =>
    api.post('/sync/incremental/background', params),

  // 后台异步同步
  backgroundSync: (params = {}) =>
    api.post('/sync/background', params),

  // 获取同步状态
  getSyncStatus: () =>
    api.get('/sync/status'),

  // 获取同步进度
  getSyncProgress: () =>
    api.get('/sync/progress'),

  // 验证数据一致性
  validateConsistency: () =>
    api.get('/sync/validate'),

  // 获取同步统计
  getSyncStatistics: () =>
    api.get('/sync/statistics'),

  // 清除同步缓存
  clearSyncCache: () =>
    api.post('/sync/clear-cache'),
}

// 用户管理API（仅管理员可用）
export const userAPI = {
  // 获取所有用户列表
  getUsers: (skip = 0, limit = 100) =>
    api.get('/auth/users', { params: { skip, limit } }),

  // 获取指定用户信息
  getUser: (userId) =>
    api.get(`/auth/users/${userId}`),

  // 创建用户
  createUser: (userData) =>
    api.post('/auth/register', userData),

  // 更新指定用户
  updateUser: (userId, userData) =>
    api.put(`/auth/users/${userId}`, userData),

  // 删除指定用户
  deleteUser: (userId) =>
    api.delete(`/auth/users/${userId}`),

  // 修改用户密码
  changePassword: (passwordData) =>
    api.post('/auth/change-password', passwordData),
}

export default api