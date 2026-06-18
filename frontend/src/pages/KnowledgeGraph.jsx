import { useEffect, useRef, useState } from 'react'
import { 
  Card, Input, Button, Space, Spin, message, 
  Row, Col, Tabs, Select, Slider, 
  Divider, Tag, Tooltip, Modal,
  List, Descriptions, Empty,
  Switch
} from 'antd'
import {
  SearchOutlined,
  DownloadOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
  ExpandOutlined,
  CompressOutlined
} from '@ant-design/icons'
import * as d3 from 'd3'
import { knowledgeGraphAPI } from '../services/api'

const { Option } = Select

// 节点类型颜色映射
const NODE_COLORS = {
  'Herb': '#52c41a',      // 绿色 - 药材
  'Prescription': '#1890ff', // 蓝色 - 方剂
  'Efficacy': '#faad14',     // 黄色 - 功效
  'Nature': '#722ed1',       // 紫色 - 性味
  'Meridian': '#eb2f96',     // 粉色 - 归经
  'Department': '#13c2c2',   // 青色 - 科室
  'Medic': '#f5222d',        // 红色 - 中成药
  'Role': '#fa8c16',         // 橙色 - 角色(君臣佐使)
  'Flavor': '#1890ff',       // 蓝色 - 味道
  'Direction': '#722ed1',    // 紫色 - 升降浮沉
  'DosageForm': '#722ed1',   // 紫色 - 剂型
  'default': '#999999'
}

// 节点类型中文映射
const NODE_LABELS_CN = {
  'Herb': '药材',
  'Prescription': '方剂',
  'Efficacy': '功效',
  'Nature': '性味',
  'Meridian': '归经',
  'Department': '科室',
  'Medic': '中成药',
  'Role': '角色',
  'Flavor': '味道',
  'Direction': '升降浮沉',
  'DosageForm': '剂型'
}

// 关系类型颜色映射 - 必须与后端返回的关系类型一致
const LINK_COLORS = {
  // 药材相关关系
  'HAS_EFFICACY': '#52c41a',    // 功效 - 绿色
  'HAS_NATURE': '#13c2c2',      // 性味 - 青色
  'ENTERS_MERIDIAN': '#f5222d', // 归经 - 红色
  'CONTAINED_BY': '#1890ff',    // 被方剂包含 - 蓝色
  
  // 方剂相关关系
  'BELONGS_TO': '#faad14',      // 属于类别 - 黄色
  'HAS_ROLE': '#eb2f96',        // 君臣佐使角色 - 粉色
  'CONTAINS': '#722ed1',        // 包含药材 - 紫色
  
  // 中成药相关关系
  'BELONGS_TO_DEPARTMENT': '#722ed1', // 属于科室
  'HAS_DOSAGE_FORM': '#722ed1',       // 剂型 - 紫色
  
  // 兼容旧名称
  'BELONGS_TO_MERIDIAN': '#f5222d',
  'CONTAINS_IN': '#1890ff',
  'CONTAINS_IN_PRESCRIPTION': '#1890ff',
  'CONTAINS_IN_MEDIC': '#1890ff',
  'CONTAINS_HERB': '#52c41a',
  'HAS_MERIDIAN': '#f5222d',
  
  'default': '#999999'
}

// 关系类型中文标签映射（用于筛选器显示）
const RELATIONSHIP_LABELS_CN = {
  'HAS_EFFICACY': '功效',
  'HAS_NATURE': '性味',
  'ENTERS_MERIDIAN': '归经',
  'CONTAINED_BY': '被方剂包含',
  'BELONGS_TO': '属于类别',
  'HAS_ROLE': '君臣佐使角色',
  'CONTAINS': '包含药材',
  'HAS_DOSAGE_FORM': '剂型'
}

// 筛选器使用的标准关系类型列表（排除兼容旧名称）
const STANDARD_RELATIONSHIP_TYPES = [
  'HAS_EFFICACY',
  'HAS_NATURE',
  'ENTERS_MERIDIAN',
  'CONTAINED_BY',
  'BELONGS_TO',
  'HAS_ROLE',
  'CONTAINS',
  'HAS_DOSAGE_FORM'
]

const KnowledgeGraph = () => {
  const svgRef = useRef(null)
  const containerRef = useRef(null)
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [searchType, setSearchType] = useState('auto') // 'auto', 'Herb', 'Prescription', 'Medic'
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [selectedNodes, setSelectedNodes] = useState([])
  const [selectedNodeInfo, setSelectedNodeInfo] = useState(null)
  const [nodeDetails, setNodeDetails] = useState(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [filterOptions, setFilterOptions] = useState({
    nodeType: 'all',
    relationshipType: 'all',
    degreeRange: [0, 100]
  })
  const [activeTab, setActiveTab] = useState('selectedNode')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showLabels, setShowLabels] = useState(true)
  const [showLinkLabels, setShowLinkLabels] = useState(false)
  const [nodeSizeByDegree, setNodeSizeByDegree] = useState(true)
  const [simulation, setSimulation] = useState(null)
  const [pagination, setPagination] = useState({
    limit: 30,
    skip: 0,
    relationshipTypes: null
  })
  const [similarNodes, setSimilarNodes] = useState([])
  const [analyzing, setAnalyzing] = useState(false)
  const [exportDepth, setExportDepth] = useState(2)
  const [isExportModalVisible, setIsExportModalVisible] = useState(false)

  // 默认加载表实感冒颗粒中成药
  useEffect(() => {
    setKeyword('表实感冒颗粒')
    // 直接调用加载，不依赖keyword状态变化
    setTimeout(() => {
      loadGraphData('表实感冒颗粒')
    }, 0)
  }, [])

  // 监听graphData的变化，自动调整度数范围
  useEffect(() => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0 && graphData.links) {
      // 计算最大度数
      const nodeDegrees = {}
      graphData.nodes.forEach(node => {
        nodeDegrees[node.id] = 0
      })
      graphData.links.forEach(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        if (nodeDegrees[sourceId] !== undefined) nodeDegrees[sourceId]++
        if (nodeDegrees[targetId] !== undefined) nodeDegrees[targetId]++
      })
      const maxDegree = Math.max(...Object.values(nodeDegrees), 10)
      // 更新度数范围的最大值
      setFilterOptions(prev => ({
        ...prev,
        degreeRange: [prev.degreeRange[0], Math.max(prev.degreeRange[1], maxDegree)]
      }))
    }
  }, [graphData])

  // BFS算法：计算从起始节点到所有其他节点的深度
  const calculateNodeDepths = (startNodeId, links, allNodes) => {
    const depths = new Map()
    const visited = new Set()
    const queue = [{ id: startNodeId, depth: 0 }]
    
    // 构建邻接表
    const adjacencyList = new Map()
    allNodes.forEach(node => adjacencyList.set(node.id, []))
    
    links.forEach(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source
      const targetId = typeof link.target === 'object' ? link.target.id : link.target
      
      if (adjacencyList.has(sourceId)) {
        adjacencyList.get(sourceId).push(targetId)
      }
      if (adjacencyList.has(targetId)) {
        adjacencyList.get(targetId).push(sourceId)
      }
    })
    
    // BFS遍历
    while (queue.length > 0) {
      const { id, depth } = queue.shift()
      
      if (visited.has(id)) continue
      visited.add(id)
      depths.set(id, depth)
      
      const neighbors = adjacencyList.get(id) || []
      neighbors.forEach(neighborId => {
        if (!visited.has(neighborId)) {
          queue.push({ id: neighborId, depth: depth + 1 })
        }
      })
    }
    
    return depths
  }

  // 统一处理所有渲染相关的状态变化（分页、筛选、显示选项）
  useEffect(() => {
    if (graphData && graphData.nodes && graphData.nodes.length > 0) {
      let filteredLinks = graphData.links
      
      // 如果指定了关系类型筛选，过滤连接
      if (pagination.relationshipTypes) {
        const allowedTypes = pagination.relationshipTypes.split(',')
        filteredLinks = graphData.links.filter(link => {
          const linkType = link.type || link.relationship
          return allowedTypes.includes(linkType)
        })
      }
      
      // 智能分页：基于BFS深度优先显示节点
      let paginatedNodes = graphData.nodes
      
      if (pagination.limit > 0 && graphData.nodes.length > pagination.limit) {
        // 获取当前选中节点的ID（取第一个选中的节点作为起始点）
        const selectedNodeId = selectedNodes.length > 0 ? selectedNodes[0] : null
        
        if (selectedNodeId) {
          // 计算从选中节点到所有其他节点的深度
          const nodeDepths = calculateNodeDepths(selectedNodeId, filteredLinks, graphData.nodes)
          
          // 按深度排序节点（深度小的优先）
          const sortedNodes = [...graphData.nodes].sort((a, b) => {
            const depthA = nodeDepths.get(a.id) !== undefined ? nodeDepths.get(a.id) : Infinity
            const depthB = nodeDepths.get(b.id) !== undefined ? nodeDepths.get(b.id) : Infinity
            return depthA - depthB
          })
          
          // 取前N个节点
          paginatedNodes = sortedNodes.slice(0, pagination.limit)
          console.log(`BFS分页: 选中节点=${selectedNodeId}, 显示节点数=${paginatedNodes.length}, 深度分布=${[...nodeDepths.values()].filter(d => d <= 3).join(',')}`)
        } else {
          // 没有选中节点时，使用普通分页
          paginatedNodes = graphData.nodes.slice(pagination.skip, pagination.skip + pagination.limit)
        }
      }
      
      // 只保留选中节点之间的连接
      const paginatedNodeIds = new Set(paginatedNodes.map(n => n.id))
      const visibleLinks = filteredLinks.filter(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        return paginatedNodeIds.has(sourceId) && paginatedNodeIds.has(targetId)
      })
      
      const paginatedData = {
        nodes: paginatedNodes,
        links: visibleLinks
      }

      console.log(`渲染图谱: 总节点数${graphData.nodes.length}, 当前显示${paginatedData.nodes.length}个节点, 连接数${visibleLinks.length}, 关系筛选=${pagination.relationshipTypes || '无'}, 选中节点=${selectedNodes.length}`)
      renderGraph(paginatedData)
    }
  }, [pagination.skip, pagination.limit, pagination.relationshipTypes, graphData, filterOptions, showLabels, showLinkLabels, nodeSizeByDegree, selectedNodes])

  // 增强药材数据：添加包含该药材的中成药和方剂
  const enhanceHerbData = async (herbData, herbName) => {
    try {
      const enhancedData = {
        nodes: [...herbData.nodes],
        links: [...herbData.links]
      }
      
      const nodeSet = new Set(herbData.nodes.map(node => node.id))
      
      // 获取包含该药材的中成药
      try {
        const herbMedicsResponse = await knowledgeGraphAPI.getHerbMedics(herbName)
        if (herbMedicsResponse.medics && herbMedicsResponse.medics.length > 0) {
          herbMedicsResponse.medics.forEach(item => {
            const medic = item.medic
            if (!nodeSet.has(medic.name)) {
              enhancedData.nodes.push({
                id: medic.name,
                name: medic.name,
                type: 2, // Medic类型
                label: 'Medic',
                labels: ['Medic'],
                ...medic
              })
              nodeSet.add(medic.name)
              
              // 添加药材到中成药的CONTAINS关系
              enhancedData.links.push({
                source: medic.name,
                target: herbName,
                type: 'CONTAINS'
              })
            }
          })
        }
      } catch (medicError) {
        console.log('获取药材相关中成药失败:', medicError)
      }
      
      // 获取包含该药材的方剂
      try {
        const herbPrescriptionsResponse = await knowledgeGraphAPI.getHerbPrescriptions(herbName)
        if (herbPrescriptionsResponse.prescriptions && herbPrescriptionsResponse.prescriptions.length > 0) {
          herbPrescriptionsResponse.prescriptions.forEach(item => {
            const prescription = item.prescription
            if (!nodeSet.has(prescription.name)) {
              enhancedData.nodes.push({
                id: prescription.name,
                name: prescription.name,
                type: 1, // Prescription类型
                label: 'Prescription',
                labels: ['Prescription'],
                ...prescription
              })
              nodeSet.add(prescription.name)
              
              // 添加药材到方剂的CONTAINS关系
              enhancedData.links.push({
                source: prescription.name,
                target: herbName,
                type: 'CONTAINS'
              })
            }
          })
        }
      } catch (prescriptionError) {
        console.log('获取药材相关方剂失败:', prescriptionError)
      }
      
      return enhancedData
    } catch (error) {
      console.log('增强药材数据失败:', error)
      return herbData
    }
  }

  // 根据搜索类型调整节点标签，确保显示正确的类型和颜色
  const adjustNodeLabelsForSearchType = (nodes, searchType) => {
    if (!nodes || !searchType || searchType === 'auto') return nodes
    
    return nodes.map(node => {
      // 复制节点以避免修改原始数据
      const adjustedNode = { ...node }
      
      // 检查节点是否具有多个标签
      if (adjustedNode.labels && adjustedNode.labels.length > 1) {
        // 如果节点的标签中包含当前搜索类型，则优先使用搜索类型
        if (adjustedNode.labels.includes(searchType)) {
          adjustedNode.label = searchType
          // 调整labels数组的顺序，将搜索类型放在第一位
          const otherLabels = adjustedNode.labels.filter(l => l !== searchType)
          adjustedNode.labels = [searchType, ...otherLabels]
        }
      }
      
      return adjustedNode
    })
  }

  const loadGraphData = async (searchKeyword = null) => {
    try {
      setLoading(true)
      // 清除旧的选中状态和详情
      setSelectedNodeInfo(null)
      setSelectedNodes([])
      setNodeDetails(null)
      let data = null
      
      // 使用传入的参数或状态中的keyword，并自动去除前后空格
      const rawKeyword = searchKeyword || keyword
      const queryKeyword = rawKeyword.trim()
      
      // 检查关键词是否为空
      if (!queryKeyword || queryKeyword === '') {
        message.warning('请输入搜索关键词')
        setLoading(false)
        return
      }
      
      // 根据搜索类型选择查询方式 - 必须首先判断，避免进入auto模式的药材查询
      console.log(`搜索关键词: "${queryKeyword}", 搜索类型: ${searchType}`)
      
      // 如果用户明确选择了搜索类型，直接跳转到对应分支，不经过auto模式
      if (searchType === 'Herb') {
        console.log('执行药材搜索逻辑')
        // 只查询药材
        try {
          const herbData = await knowledgeGraphAPI.getHerbRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          if (herbData.nodes && herbData.nodes.length > 0) {
            // 增强药材数据：添加包含该药材的中成药和方剂
            const enhancedData = await enhanceHerbData(herbData, queryKeyword)
            data = enhancedData
            console.log('找到药材关系(增强后):', enhancedData)
          } else {
            // 药材查询没有结果，提示用户可能是其他类型
            message.warning(`"${queryKeyword}" 可能不是药材，请尝试选择"方剂"、"中成药"或"自动识别"`)
          }
        } catch (herbError) {
          console.log('药材查询失败:', herbError)
          message.error('查询药材失败')
        }
      } else if (searchType === 'Medic') {
        console.log('执行中成药搜索逻辑')
        // 只查询中成药
        try {
          const medicData = await knowledgeGraphAPI.getMedicRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          const hasMedicNode = medicData.nodes && medicData.nodes.some(node =>
            node.label === 'Medic' || (node.labels && node.labels.includes('Medic'))
          )
          if (hasMedicNode) {
            data = medicData
            console.log('找到中成药关系:', medicData)
          } else {
            // 中成药查询没有结果，提示用户可能是其他类型
            message.warning(`"${queryKeyword}" 可能不是中成药，请尝试选择"方剂"或"自动识别"`)
          }
        } catch (medicError) {
          console.log('中成药查询失败:', medicError)
          message.error('查询中成药失败')
        }
      } else if (searchType === 'Prescription') {
        console.log('执行方剂搜索逻辑')
        // 只查询方剂
        try {
          const prescriptionData = await knowledgeGraphAPI.getPrescriptionRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          const hasPrescriptionNode = prescriptionData.nodes && prescriptionData.nodes.some(node =>
            node.label === 'Prescription' || (node.labels && node.labels.includes('Prescription'))
          )
          if (hasPrescriptionNode) {
            data = prescriptionData
            console.log('找到方剂关系:', prescriptionData)
          } else {
            // 方剂查询没有结果，提示用户并清空数据
            message.warning(`"${queryKeyword}" 可能不是方剂，请尝试选择"中成药"或"自动识别"`)
            data = { nodes: [], links: [] } // 关键：清空数据，避免显示旧结果
          }
        } catch (prescriptionError) {
          console.log('方剂查询失败:', prescriptionError)
          message.error('查询方剂失败')
          data = { nodes: [], links: [] } // 关键：出错时也清空数据
        }
      } else if (searchType === 'auto') {
        // 自动识别模式：依次尝试查询（后端返回所有数据，前端进行分页）
        // 1. 先尝试查询药材
        try {
          const herbData = await knowledgeGraphAPI.getHerbRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          if (herbData.nodes && herbData.nodes.length > 0 && herbData.links && herbData.links.length > 0) {
            // 增强药材数据：添加包含该药材的中成药和方剂
            const enhancedData = await enhanceHerbData(herbData, queryKeyword)
            data = enhancedData
            console.log('找到药材关系(增强后):', enhancedData)
          }
        } catch (herbError) {
          console.log('药材查询失败:', herbError)
        }

        // 2. 如果没有找到药材关系，尝试查询中成药
        if (!data) {
          try {
            const medicData = await knowledgeGraphAPI.getMedicRelationships(
              queryKeyword,
              2,
              0, // 不限制limit，获取所有数据
              0, // skip为0
              pagination.relationshipTypes
            )
            const hasMedicNode = medicData.nodes && medicData.nodes.some(node =>
              node.label === 'Medic' || (node.labels && node.labels.includes('Medic'))
            )
            if (hasMedicNode) {
              data = medicData
              console.log('找到中成药关系:', medicData)
            }
          } catch (medicError) {
            console.log('中成药查询失败:', medicError)
          }
        }

        // 3. 如果没有找到中成药关系，尝试查询方剂
        if (!data) {
          try {
            const prescriptionData = await knowledgeGraphAPI.getPrescriptionRelationships(
              queryKeyword,
              2,
              0, // 不限制limit，获取所有数据
              0, // skip为0
              pagination.relationshipTypes
            )
            const hasPrescriptionNode = prescriptionData.nodes && prescriptionData.nodes.some(node =>
              node.label === 'Prescription' || (node.labels && node.labels.includes('Prescription'))
            )
            if (hasPrescriptionNode) {
              data = prescriptionData
              console.log('找到方剂关系:', prescriptionData)
            }
          } catch (prescriptionError) {
            console.log('方剂查询失败:', prescriptionError)
          }
        }
      } else if (searchType === 'Herb') {
        console.log('执行药材搜索逻辑')
        // 只查询药材
        try {
          const herbData = await knowledgeGraphAPI.getHerbRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          if (herbData.nodes && herbData.nodes.length > 0) {
            // 增强药材数据：添加包含该药材的中成药和方剂
            const enhancedData = await enhanceHerbData(herbData, queryKeyword)
            data = enhancedData
            console.log('找到药材关系(增强后):', enhancedData)
          } else {
            // 药材查询没有结果，提示用户可能是其他类型
            message.warning(`"${queryKeyword}" 可能不是药材，请尝试选择"方剂"、"中成药"或"自动识别"`)
          }
        } catch (herbError) {
          console.log('药材查询失败:', herbError)
          message.error('查询药材失败')
        }
      } else if (searchType === 'Medic') {
        console.log('执行中成药搜索逻辑')
        // 只查询中成药
        try {
          const medicData = await knowledgeGraphAPI.getMedicRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          if (medicData.nodes && medicData.nodes.length > 0) {
            data = medicData
            console.log('找到中成药关系:', medicData)
          } else {
            // 中成药查询没有结果，提示用户可能是其他类型
            message.warning(`"${queryKeyword}" 可能不是中成药，请尝试选择"方剂"或"自动识别"`)
          }
        } catch (medicError) {
          console.log('中成药查询失败:', medicError)
          message.error('查询中成药失败')
        }
      } else if (searchType === 'Prescription') {
        console.log('执行方剂搜索逻辑')
        // 只查询方剂
        try {
          const prescriptionData = await knowledgeGraphAPI.getPrescriptionRelationships(
            queryKeyword,
            2,
            0, // 不限制limit，获取所有数据
            0, // skip为0
            pagination.relationshipTypes
          )
          if (prescriptionData.nodes && prescriptionData.nodes.length > 0) {
            data = prescriptionData
            console.log('找到方剂关系:', prescriptionData)
          } else {
            // 方剂查询没有结果，提示用户可能是其他类型
            message.warning(`"${queryKeyword}" 可能不是方剂，请尝试选择"中成药"或"自动识别"`)
          }
        } catch (prescriptionError) {
          console.log('方剂查询失败:', prescriptionError)
          message.error('查询方剂失败')
        }
      }
      
      // 如果都没有找到，显示提示
      if (!data || !data.nodes || data.nodes.length === 0) {
        console.log(`搜索结果为空: keyword="${queryKeyword}", searchType=${searchType}`)
        message.warning(`未找到 "${queryKeyword}" 的相关信息，请检查名称是否正确`)
        data = { nodes: [], links: [] }
      } else {
        console.log(`搜索成功: 找到 ${data.nodes.length} 个节点, ${data.links.length} 条关系`)
      }

      // 根据搜索类型调整节点标签，确保显示正确的类型和颜色
      if (data && data.nodes && data.nodes.length > 0) {
        data.nodes = adjustNodeLabelsForSearchType(data.nodes, searchType)
      }

      // 保存完整数据到state
      setGraphData(data)

      // 实现分页逻辑：根据pagination.limit和pagination.skip截取数据
      const totalNodes = data.nodes.length
      const paginatedData = {
        nodes: data.nodes.slice(pagination.skip, pagination.skip + pagination.limit),
        links: data.links // 连接暂时不分页，根据节点分页结果动态过滤
      }

      console.log(`分页信息: 总节点数${totalNodes}, 当前显示${paginatedData.nodes.length}个节点 (skip=${pagination.skip}, limit=${pagination.limit})`)

      renderGraph(paginatedData)
      
      // 自动选中搜索的节点（如果有数据）
      if (data && data.nodes && data.nodes.length > 0) {
        // 尝试找到名称与关键词精确匹配的节点，否则选择第一个节点
        const matchedNode = data.nodes.find(node => 
          node.name && node.name.toLowerCase() === queryKeyword.toLowerCase()
        ) || data.nodes[0]
        
        if (matchedNode) {
          setSelectedNodes([matchedNode.id])
          setSelectedNodeInfo(matchedNode)
          loadNodeDetails(matchedNode)
        }
      }
    } catch (error) {
      message.error('加载知识图谱失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const debugDatabase = async () => {
    try {
      const response = await knowledgeGraphAPI.debugDatabaseInfo()
      console.log('数据库调试信息:', response)
      message.info(`数据库连接正常，找到 ${response.herb_count} 个药材节点`)
    } catch (error) {
      console.error('调试失败:', error)
      message.error('调试失败')
    }
  }

  const loadNodeDetails = async (node) => {
    try {
      setLoadingDetails(true)
      const nodeLabel = node.label || (node.labels && node.labels[0])
      let details = null
      
      console.log('loadNodeDetails called with node:', node)
      console.log('当前搜索类型:', searchType)
      
      // 智能决定使用哪个API
      // 1. 如果节点有明确的标签，优先使用节点标签
      // 2. 如果节点有多个标签，使用当前搜索类型
      // 3. 如果节点没有标签或标签未知，使用当前搜索类型
      
      let requestType = null
      
      // 检查节点是否有明确的单一标签
      if (node.labels && node.labels.length === 1) {
        // 只有一个标签，使用它
        requestType = node.labels[0]
        console.log(`节点有单一标签: ${requestType}`)
      } else if (node.labels && node.labels.length > 1) {
        // 有多个标签，使用当前搜索类型
        // 但需要确保当前搜索类型在节点的标签中
        if (searchType && node.labels.includes(searchType)) {
          requestType = searchType
          console.log(`节点有多个标签，使用当前搜索类型: ${requestType}`)
        } else {
          // 当前搜索类型不在节点标签中，使用第一个标签
          requestType = node.labels[0]
          console.log(`搜索类型${searchType}不在节点标签中，使用第一个标签: ${requestType}`)
        }
      } else {
        // 没有标签信息，使用当前搜索类型
        requestType = searchType || nodeLabel
        console.log(`没有标签信息，使用: ${requestType}`)
      }
      
      // 确保requestType是有效的
      if (requestType && ['Herb', 'Prescription', 'Medic'].includes(requestType)) {
        details = await knowledgeGraphAPI.getNodeDetails(node.name, requestType)
        console.log(`${requestType}详情API响应:`, details)
      } else {
        console.error(`无效的请求类型: ${requestType}`)
      }
      
      // 检查API响应结构
      if (details && details.details) {
        console.log('details.details内容:', details.details)
      }
      
      // 仅在调试模式下显示实际标签差异，不强制更新节点类型
      if (details && details.actual_labels && details.actual_labels.length > 0) {
        const actualLabel = details.actual_labels[0]
        const currentNodeLabel = node.label || (node.labels && node.labels[0])
        // 如果实际类型与当前类型不同，在控制台输出警告但不更新UI
        if (actualLabel && actualLabel !== currentNodeLabel) {
          console.warn(`注意: 节点"${node.name}"的搜索类型是${currentNodeLabel}，但实际类型是${actualLabel}`)
          console.warn(`建议: 检查搜索关键词是否准确，或尝试其他搜索类型`)
        }
      }
      
      setNodeDetails(details)
    } catch (error) {
      console.error('加载节点详情失败:', error)
      message.error('加载节点详情失败')
    } finally {
      setLoadingDetails(false)
    }
  }

  const renderHerbDetails = (details) => {
    if (!details) return null
    
    // 根据API实际响应结构调整字段映射
    const herb = details.details?.herb || details.herb || details
    const natures = details.details?.natures || details.natures || []
    const meridians = details.details?.meridians || details.meridians || []
    const efficacies = details.details?.efficacies || details.efficacies || []
    const prescriptions = details.details?.prescriptions || details.prescriptions || []
    
    // 处理性味字段：优先使用natures数组，如果没有则使用herb.nature
    const natureText = natures.length > 0 ? natures.join('，') : (herb.nature || herb.性味 || '')
    
    // 处理功效字段：优先使用efficacies数组，如果没有则使用herb.function
    const efficacyText = efficacies.length > 0 ? efficacies.join('，') : (herb.function || herb.功效 || '')
    
    return (
      <div style={{ fontSize: '12px' }}>
        {/* 基本信息 */}
        <p><strong>ID:</strong> {herb.id || ''}</p>
        <p><strong>拼音:</strong> {herb.pinyin || herb.拼音注音 || ''}</p>
        <p><strong>英文名:</strong> {herb.english_name || herb.englishName || ''}</p>
        <p><strong>别名:</strong> {herb.aliases || herb.别名 || ''}</p>
        
        {/* 药性 */}
        <p><strong>性味:</strong> {natureText}</p>
        <p><strong>归经:</strong> {meridians.length > 0 ? meridians.join('，') : (herb.meridians || herb.归经 || '暂无数据')}</p>
        <p><strong>功能主治:</strong> {efficacyText}</p>
        
        {/* 用法与来源 */}
        <p><strong>用法用量:</strong> {herb.usage || herb.用法用量 || ''}</p>
        <p><strong>药材基源:</strong> {herb.source || herb.药材基源 || ''}</p>
        
        {/* 生境与形态 */}
        {herb.habitat && <p><strong>生境分布:</strong> {herb.habitat}</p>}
        {herb.original_morphology && <p><strong>原形态:</strong> {herb.original_morphology}</p>}
        {herb.properties && <p><strong>性状:</strong> {herb.properties}</p>}
        
        {/* 化学与药理 */}
        {herb.chemical_composition && <p><strong>化学成分:</strong> {herb.chemical_composition}</p>}
        {herb.pharmacological_effects && <p><strong>药理作用:</strong> {herb.pharmacological_effects}</p>}
        
        {/* 炮制与储藏 */}
        {herb.processing && <p><strong>炮制:</strong> {herb.processing}</p>}
        {herb.harvest_storage && <p><strong>采收和储藏:</strong> {herb.harvest_storage}</p>}
        {herb.storage && <p><strong>贮藏:</strong> {herb.storage}</p>}
        
        {/* 临床应用与鉴别 */}
        {herb.clinical_application && <p><strong>临床应用:</strong> {herb.clinical_application}</p>}
        {herb.identification && <p><strong>鉴别:</strong> {herb.identification}</p>}
        
        {/* 论述与摘录 */}
        {herb.discussions && <p><strong>各家论述:</strong> {herb.discussions}</p>}
        {herb.excerpt && <p><strong>摘录:</strong> {herb.excerpt}</p>}
        
        {/* 出处 */}
        {herb.source_text && <p><strong>出处:</strong> {herb.source_text}</p>}
        
        {/* 所属方剂 */}
        {prescriptions && prescriptions.length > 0 && (
          <p><strong>所属方剂:</strong> {prescriptions.map(p => p.name || p.prescription?.name).join('、')}</p>
        )}
      </div>
    )
  }

  const renderPrescriptionDetails = (details) => {
    if (!details) return null
    
    // 后端返回的数据结构是嵌套的：details.details 包含详细信息
    const detailData = details.details || details
    const prescription = detailData.prescription || detailData
    const herbs = detailData.herbs || []
    const efficacies = detailData.efficacies || []
    const category = detailData.categories || detailData.category || ''
    
    // 处理组成字段：优先使用herbs数组，如果没有则从prescription字段提取
    let compositionText = herbs.join('、')
    if (!compositionText && prescription.prescription) {
      // 从处方原文中提取药材名称（简单的中文分词）
      const prescriptionText = prescription.prescription
      const herbMatches = prescriptionText.match(/[一-龥]{2,4}(?=[、，,]|$)/g) || []
      if (herbMatches.length > 0) {
        compositionText = herbMatches.join('、')
      } else {
        compositionText = prescription.prescription
      }
    }
    
    // 处理功效字段：优先使用efficacies数组，如果没有则使用中文字段
    // 从调试信息看到，实际字段名是 function_indication
    const efficacyText = efficacies.length > 0 ? efficacies.join('，') : (
      prescription.function_indication ||  // 实际字段名：function_indication
      detailData.function_indication ||  // 新增：从detailData直接获取
      prescription.efficacies?.join('，') || 
      prescription.function || 
      prescription.功能 || 
      prescription.功能主治 || 
      prescription["功能"] || 
      prescription["功能主治"] || 
      ''
    )
    
    return (
      <div style={{ fontSize: '12px' }}>
        {/* 基本信息 */}
        <p><strong>ID:</strong> {prescription.id || ''}</p>
        <p><strong>方剂名称:</strong> {prescription.name || prescription.chinese_name || ''}</p>
        
        {/* 组成与功效 */}
        <p><strong>组成:</strong> {compositionText || prescription.composition || ''}</p>
        <p><strong>功能主治:</strong> {efficacyText || prescription.function_indication || ''}</p>
        
        {/* 用法与来源 */}
        <p><strong>用法用量:</strong> {prescription.usage_dosage || prescription.usage_method || prescription.usage || ''}</p>
        <p><strong>数据来源:</strong> {prescription.source || ''}</p>
        
        {/* 其他可选字段 */}
        {category && <p><strong>分类:</strong> {typeof category === 'object' ? category.name : category}</p>}
        {prescription.department && <p><strong>适用科室:</strong> {prescription.department}</p>}
        {prescription.prescription && <p><strong>处方原文:</strong> {prescription.prescription}</p>}
      </div>
    )
  }

  const renderDetailsSmart = (details, nodeInfo) => {
    if (!details) return null
    
    console.log('智能渲染函数接收到的数据:', details)
    console.log('节点信息:', nodeInfo)
    
    // 检查数据结构，根据实际数据决定渲染哪个组件
    const detailsData = details.details || details
    
    // 检查是否是中成药数据
    if (detailsData.medic || (typeof detailsData === 'object' && 'medic' in detailsData)) {
      console.log('检测到中成药数据，使用renderMedicDetails')
      return renderMedicDetails(details)
    }
    
    // 检查是否是方剂数据
    if (detailsData.prescription || (typeof detailsData === 'object' && 'prescription' in detailsData)) {
      console.log('检测到方剂数据，使用renderPrescriptionDetails')
      return renderPrescriptionDetails(details)
    }
    
    // 检查是否是药材数据
    if (detailsData.herb || (typeof detailsData === 'object' && 'herb' in detailsData)) {
      console.log('检测到药材数据，使用renderHerbDetails')
      return renderHerbDetails(details)
    }
    
    // 如果无法识别数据结构，根据节点标签决定
    console.log('无法识别数据结构，根据节点标签决定')
    const nodeLabel = nodeInfo.label || (nodeInfo.labels && nodeInfo.labels[0])
    
    if (nodeLabel === 'Herb' || nodeInfo.labels?.includes('Herb')) {
      return renderHerbDetails(details)
    } else if (nodeLabel === 'Prescription' || nodeInfo.labels?.includes('Prescription')) {
      return renderPrescriptionDetails(details)
    } else if (nodeLabel === 'Medic' || nodeInfo.labels?.includes('Medic')) {
      return renderMedicDetails(details)
    }
    
    // 默认返回null
    return null
  }

  const renderMedicDetails = (details) => {
    if (!details) return null
    
    console.log('renderMedicDetails接收到的数据:', details)
    
    // 中成药数据结构 - 集成所有管理字段
    const medic = details.medic || details.details?.medic || details
    
    console.log('解析后的medic对象:', medic)
    console.log('medic属性:', Object.keys(medic || {}))
    
    // 基本信息
    const id = medic.id || ''
    const name = medic.name || medic.中文名称 || ''
    const englishName = medic.english_name || medic.英文名称 || ''
    const department = medic.category || medic.科室类别 || ''
    const mainCategory = medic.main_category || medic.大类 || ''
    const subCategory = medic.sub_category || medic.小类 || ''
    
    // 功能主治
    const functionIndication = medic.function_indication || medic.功能主治 || medic.function_desc || medic.功能与主治 || ''
    
    // 药物组成
    const ingredients = medic.composition || medic.药物组成 || medic.ingredients || []
    
    // 规格和用法
    const specification = medic.specification || medic.规格 || medic.specifications || ''
    const usageDosage = medic.usage_dosage || medic.用法用量 || medic.usage || medic.用法与用量 || ''
    
    // 方解和临床应用
    const analysis = medic.analysis || medic.方解 || ''
    const clinicalApplication = medic.clinical_application || medic.临床应用 || ''
    
    // 安全性信息
    const sideEffects = medic.side_effects || medic.不良反应 || medic.adverse_reactions || ''
    const contraindications = medic.contraindications || medic.禁忌 || ''
    const precautions = medic.precautions || medic.注意事项 || ''
    
    // 药理和参考文献
    const pharmacology = medic.pharmacology || medic.药理毒理 || medic.pharmacological || ''
    const references = medic.references || medic.参考文献 || ''
    const source = medic.source || medic.数据来源 || ''
    
    // 君臣佐使
    const monarchMinisters = medic.monarch_ministers_assistants_couriers || medic.君臣佐使 || ''
    
    // 解析君臣佐使
    const monarchMatch = monarchMinisters.match(/君药[：:]([^。]+)/)
    const ministerMatch = monarchMinisters.match(/臣药[：:]([^。]+)/)
    const assistantMatch = monarchMinisters.match(/佐药[：:]([^。]+)/)
    const guideMatch = monarchMinisters.match(/使药[：:]([^。]+)/)
    
    const monarch = medic.monarch || (monarchMatch ? monarchMatch[1].trim() : '')
    const minister = medic.minister || (ministerMatch ? ministerMatch[1].trim() : '')
    const assistant = medic.assistant || (assistantMatch ? assistantMatch[1].trim() : '')
    const guide = medic.guide || (guideMatch ? guideMatch[1].trim() : '')

    return (
      <div style={{ fontSize: '11px' }}>
        {/* 调试信息 */}
        <div style={{ display: 'none' }} data-debug="medic-data">
          {JSON.stringify(medic, null, 2)}
        </div>
        
        {/* 基本信息 */}
        <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>基本信息</Divider>
        <p><strong>ID:</strong> {id || '暂无'}</p>
        <p><strong>中文名称:</strong> {name || '暂无'}</p>
        {englishName && <p><strong>英文名称:</strong> {englishName}</p>}
        {department && <p><strong>科室类别:</strong> {department}</p>}
        {mainCategory && <p><strong>大类:</strong> {mainCategory}</p>}
        {subCategory && <p><strong>小类:</strong> {subCategory}</p>}
        
        {/* 功能主治 */}
        <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>功能主治</Divider>
        <p><strong>功能主治:</strong> {functionIndication || '暂无'}</p>
        {clinicalApplication && <p><strong>临床应用:</strong> {clinicalApplication}</p>}
        
        {/* 药物组成 */}
        <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>药物组成</Divider>
        <p><strong>药物组成:</strong> {Array.isArray(ingredients) ? (ingredients.length > 0 ? ingredients.join('、') : '暂无') : ingredients || '暂无'}</p>
        {analysis && <p><strong>方解:</strong> {analysis}</p>}
        
        {/* 用法用量 */}
        <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>用法用量</Divider>
        <p><strong>用法用量:</strong> {usageDosage || '暂无'}</p>
        {specification && <p><strong>规格:</strong> {specification}</p>}
        
        {/* 君臣佐使 */}
        {(monarch || minister || assistant || guide) && (
          <>
            <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>君臣佐使</Divider>
            {monarch && <p><strong>君药:</strong> {monarch}</p>}
            {minister && <p><strong>臣药:</strong> {minister}</p>}
            {assistant && <p><strong>佐药:</strong> {assistant}</p>}
            {guide && <p><strong>使药:</strong> {guide}</p>}
          </>
        )}
        
        {/* 安全性信息 */}
        {(contraindications || precautions || sideEffects) && (
          <>
            <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>安全性信息</Divider>
            {contraindications && <p><strong>禁忌:</strong> {contraindications}</p>}
            {precautions && <p><strong>注意事项:</strong> {precautions}</p>}
            {sideEffects && <p><strong>不良反应:</strong> {sideEffects}</p>}
          </>
        )}
        
        {/* 药理研究 */}
        {(pharmacology || references) && (
          <>
            <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>药理研究</Divider>
            {pharmacology && <p><strong>药理毒理:</strong> {pharmacology}</p>}
            {references && <p><strong>参考文献:</strong> {references}</p>}
          </>
        )}
        
        {/* 数据来源 */}
        {source && (
          <>
            <Divider orientation="left" style={{ fontSize: '12px', margin: '8px 0' }}>数据来源</Divider>
            <p><strong>来源:</strong> {source}</p>
          </>
        )}
      </div>
    )
  }

  // BFS获取指定深度的子图
  const getSubgraphByDepth = (startNodeIds, maxDepth) => {
    // 确保所有ID都是字符串类型
    const normalizedStartIds = startNodeIds.map(id => String(id))
    const resultNodeIds = new Set(normalizedStartIds)
    const resultLinks = []
    const currentDepthNodes = new Set(normalizedStartIds)
    
    console.log('BFS导出: 起始节点=', normalizedStartIds, '深度=', maxDepth)
    
    for (let depth = 0; depth < maxDepth; depth++) {
      const nextDepthNodes = new Set()
      
      graphData.links.forEach(link => {
        const sourceId = String(typeof link.source === 'object' ? link.source.id : link.source)
        const targetId = String(typeof link.target === 'object' ? link.target.id : link.target)
        
        // 如果当前边的任一端在当前深度层，将另一端加入下一层
        if (currentDepthNodes.has(sourceId) && !resultNodeIds.has(targetId)) {
          nextDepthNodes.add(targetId)
          resultNodeIds.add(targetId)
          resultLinks.push(link)
        } else if (currentDepthNodes.has(targetId) && !resultNodeIds.has(sourceId)) {
          nextDepthNodes.add(sourceId)
          resultNodeIds.add(sourceId)
          resultLinks.push(link)
        } else if (currentDepthNodes.has(sourceId) || currentDepthNodes.has(targetId)) {
          // 两端都已在结果中，只添加连接
          resultLinks.push(link)
        }
      })
      
      console.log(`BFS深度${depth + 1}: 发现${nextDepthNodes.size}个新节点`)
      
      if (nextDepthNodes.size === 0) break
      currentDepthNodes.clear()
      nextDepthNodes.forEach(id => currentDepthNodes.add(id))
    }
    
    // 添加起点之间的连接
    graphData.links.forEach(link => {
      const sourceId = String(typeof link.source === 'object' ? link.source.id : link.source)
      const targetId = String(typeof link.target === 'object' ? link.target.id : link.target)
      if (normalizedStartIds.includes(sourceId) && normalizedStartIds.includes(targetId)) {
        resultLinks.push(link)
      }
    })
    
    const resultNodes = graphData.nodes.filter(n => resultNodeIds.has(String(n.id)))
    
    console.log(`BFS导出完成: 共${resultNodes.length}个节点, ${resultLinks.length}条连接`)
    
    // 去重连接
    const uniqueLinks = []
    const linkSet = new Set()
    resultLinks.forEach(link => {
      const sourceId = String(typeof link.source === 'object' ? link.source.id : link.source)
      const targetId = String(typeof link.target === 'object' ? link.target.id : link.target)
      const key = `${sourceId}-${targetId}`
      if (!linkSet.has(key)) {
        linkSet.add(key)
        uniqueLinks.push(link)
      }
    })
    
    // 规范化导出数据：links的source和target只存储ID，清理可视化字段
    const cleanedNodes = resultNodes.map(node => {
      const { x, y, vx, vy, fx, fy, index, ...rest } = node
      return rest
    })
    
    const cleanedLinks = uniqueLinks.map(link => {
      const sourceId = String(typeof link.source === 'object' ? link.source.id : link.source)
      const targetId = String(typeof link.target === 'object' ? link.target.id : link.target)
      const { source, target, index, ...rest } = link
      return {
        ...rest,
        source: sourceId,
        target: targetId
      }
    })
    
    return { nodes: cleanedNodes, links: cleanedLinks }
  }

  const showExportModal = () => {
    if (selectedNodes.length === 0) {
      message.warning('请先选择至少一个节点')
      return
    }
    setIsExportModalVisible(true)
  }

  const handleExport = async () => {
    try {
      setIsExportModalVisible(false)
      
      // 使用最后选中的单个节点作为起始点（而不是所有选中节点）
      const startNodeId = selectedNodeInfo ? selectedNodeInfo.id : null
      
      if (!startNodeId) {
        message.error('没有选中的节点')
        return
      }
      
      console.log(`导出: 起始节点=${startNodeId}, 深度=${exportDepth}`)
      
      // 使用BFS获取指定深度的子图
      const subgraph = getSubgraphByDepth([startNodeId], exportDepth)
      
      const filename = `subgraph-${startNodeId}-depth${exportDepth}-${new Date().getTime()}.json`
      
      // 导出JSON文件
      const blob = new Blob([JSON.stringify(subgraph, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      
      message.success(`导出成功：以"${startNodeId}"为中心，${subgraph.nodes.length}个节点, ${subgraph.links.length}条连接`)
    } catch (error) {
      message.error('导出失败: ' + error.message)
      console.error(error)
    }
  }

  const exportGraphImage = () => {
    const svg = svgRef.current
    if (!svg) {
      message.error('没有找到图谱内容')
      return
    }
    
    try {
      // 克隆SVG元素以避免修改原始DOM
      const svgClone = svg.cloneNode(true)
      
      // 确保SVG有正确的命名空间
      svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
      svgClone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink')
      
      // 获取SVG的尺寸
      const svgRect = svg.getBoundingClientRect()
      const width = svgRect.width || 800
      const height = svgRect.height || 600
      
      svgClone.setAttribute('width', width)
      svgClone.setAttribute('height', height)
      
      const svgData = new XMLSerializer().serializeToString(svgClone)
      
      const canvas = document.createElement('canvas')
      canvas.width = width * 2  // 高分辨率
      canvas.height = height * 2
      const ctx = canvas.getContext('2d')
      
      // 白色背景
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      
      const img = new Image()
      
      img.onload = () => {
        try {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
          const pngFile = canvas.toDataURL('image/png')
          const downloadLink = document.createElement('a')
          downloadLink.download = `knowledge-graph-${new Date().getTime()}.png`
          downloadLink.href = pngFile
          downloadLink.click()
          message.success('图片导出成功')
        } catch (err) {
          console.error('Canvas绘制失败:', err)
          message.error('图片导出失败：绘制失败')
        }
      }
      
      img.onerror = (err) => {
        console.error('图片加载失败:', err)
        message.error('图片导出失败：SVG加载失败')
      }
      
      // 使用UTF-8编码的SVG数据
      const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' })
      const url = URL.createObjectURL(svgBlob)
      img.src = url
      
      // 清理URL对象
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      console.error('导出图片失败:', error)
      message.error('图片导出失败：' + error.message)
    }
  }

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
    setTimeout(() => renderGraph(graphData), 100)
  }

  const renderGraph = (data) => {
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const container = containerRef.current
    const width = container ? container.clientWidth : 1000
    const height = isFullscreen ? window.innerHeight - 200 : 600

    // 完整数据
    const allNodes = data.nodes || []
    const allLinks = data.links || []

    // 根据节点类型过滤
    let nodes = [...allNodes]
    if (filterOptions.nodeType !== 'all') {
      nodes = nodes.filter(node => {
        const label = node.label || (node.labels && node.labels[0]) || ''
        return label === filterOptions.nodeType
      })
    }

    // 只保留连接到当前显示节点的连接
    let links = [...allLinks]
    const nodeIds = new Set(nodes.map(n => n.id))
    links = links.filter(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source
      const targetId = typeof link.target === 'object' ? link.target.id : link.target
      return nodeIds.has(sourceId) || nodeIds.has(targetId)
    })

    // 去重links（相同source和target的连接只保留一个）
    const linkSet = new Set()
    links = links.filter(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source
      const targetId = typeof link.target === 'object' ? link.target.id : link.target
      // 确保两个ID都存在且不为空
      if (!sourceId || !targetId) return false
      // 排除自连接
      if (sourceId === targetId) return false
      // 创建唯一键
      const linkKey = `${sourceId}-${targetId}`
      if (linkSet.has(linkKey)) return false
      linkSet.add(linkKey)
      return true
    })

    // 计算当前显示节点的度数（基于显示的连接）
    const nodeDegrees = {}
    nodes.forEach(node => {
      nodeDegrees[node.id] = 0
    })
    links.forEach(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source
      const targetId = typeof link.target === 'object' ? link.target.id : link.target
      if (nodeDegrees[sourceId] !== undefined) nodeDegrees[sourceId]++
      if (nodeDegrees[targetId] !== undefined) nodeDegrees[targetId]++
    })

    // 根据度数范围过滤节点（使用显示数据的度数）
    if (filterOptions.degreeRange && filterOptions.degreeRange.length === 2) {
      const [minDegree, maxDegree] = filterOptions.degreeRange
      const filteredNodeIds = nodes.filter(node => {
        const degree = nodeDegrees[node.id] || 0
        return degree >= minDegree && degree <= maxDegree
      }).map(n => n.id)

      nodes = nodes.filter(node => filteredNodeIds.includes(node.id))
      links = links.filter(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        return filteredNodeIds.includes(sourceId) && filteredNodeIds.includes(targetId)
      })

      // 重新计算过滤后的度数
      const filteredNodeDegrees = {}
      nodes.forEach(node => {
        filteredNodeDegrees[node.id] = 0
      })
      links.forEach(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        if (filteredNodeDegrees[sourceId] !== undefined) filteredNodeDegrees[sourceId]++
        if (filteredNodeDegrees[targetId] !== undefined) filteredNodeDegrees[targetId]++
      })
      // 更新度数为过滤后的值
      Object.assign(nodeDegrees, filteredNodeDegrees)
    }

    // 缩放功能
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    const g = svg.append('g')

    // 力导向模拟
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(d => {
        // 根据连接数（度数）计算碰撞半径，与节点大小保持一致
        const degree = nodeDegrees[d.id] || 1
        return nodeSizeByDegree ? 20 + Math.min(degree * 3, 30) : 25
      }))
      // 添加边界限制，防止节点跑出画布
      .force('boundary', d3.forceX(width / 2).strength(0.05))
      .force('boundaryY', d3.forceY(height / 2).strength(0.05))

    setSimulation(sim)

    // 箭头标记
    svg.append('defs').selectAll('marker')
      .data(['end'])
      .enter().append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#999')

    // 边
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', (d) => LINK_COLORS[d.type] || LINK_COLORS.default)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d) => Math.sqrt(d.weight || 1) + 1)
      .attr('marker-end', 'url(#arrow)')

    // 边标签
    const linkLabel = showLinkLabels ? g.append('g')
      .selectAll('text')
      .data(links)
      .enter()
      .append('text')
      .text((d) => RELATIONSHIP_LABELS_CN[d.type] || d.type || '')
      .attr('font-size', '10px')
      .attr('fill', '#666')
      .attr('text-anchor', 'middle')
      .attr('dy', -5)
      .style('pointer-events', 'none')
    : null

    // 节点
    const node = g.append('g')
      .selectAll('circle')
      .data(nodes)
      .enter()
      .append('circle')
      .attr('r', (d) => {
        // 根据连接数（度数）计算节点大小，与方剂和药材保持一致
        const degree = nodeDegrees[d.id] || 1
        return nodeSizeByDegree ? 15 + Math.min(degree * 2, 25) : 20
      })
      .attr('fill', (d) => {
        const label = d.label || (d.labels && d.labels[0]) || 'default'
        return NODE_COLORS[label] || NODE_COLORS.default
      })
      .attr('stroke', (d) => selectedNodes.includes(d.id) ? '#ff4d4f' : '#fff')
      .attr('stroke-width', (d) => selectedNodes.includes(d.id) ? 4 : 2)
      .style('cursor', 'pointer')
      .call(
        d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended)
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        handleNodeClick(d)
      })
      .on('dblclick', (event, d) => {
        event.stopPropagation()
        expandNode(d)
      })

    // 节点悬停效果
    node.append('title')
      .text((d) => {
        const label = d.label || (d.labels && d.labels[0]) || 'Unknown'
        const degree = nodeDegrees[d.id] || 0
        
        // 根据节点类型显示不同的提示信息
        if (label === 'Medic') {
          return `${d.name}\n类型: 中成药（第一层）\n连接数: ${degree}`
        } else if (label === 'Role') {
          const roleName = d.role_name || d.name || '角色'
          const parentMedic = d.parent_medic || ''
          return `${roleName}\n类型: 君臣佐使角色（第二层）\n所属中成药: ${parentMedic}\n连接数: ${degree}`
        } else if (label === 'Herb') {
          const roleType = d.role_type || '成分'
          return `${d.name}\n类型: 药材成分（第三层）\n角色: ${roleType}\n连接数: ${degree}`
        }
        
        return `${d.name}\n类型: ${label}\n连接数: ${degree}`
      })

    // 节点标签
    const label = showLabels ? g.append('g')
      .selectAll('text')
      .data(nodes)
      .enter()
      .append('text')
      .text((d) => {
        const nodeLabel = d.label || (d.labels && d.labels[0]) || 'Unknown'
        // 对于君臣佐使角色节点，显示为"中成药名-角色名"格式
        if (nodeLabel === 'Role' && d.parent_medic) {
          return `${d.parent_medic}-${d.name}`
        }
        return d.name
      })
      .attr('font-size', (d) => {
        const nodeLabel = d.label || (d.labels && d.labels[0]) || 'Unknown'
        // 角色节点字体稍小以适应更长文本
        return nodeLabel === 'Role' ? '10px' : '12px'
      })
      .attr('dx', (d) => {
        // 根据连接数（度数）调整标签位置，与节点大小保持一致
        const degree = nodeDegrees[d.id] || 1
        return nodeSizeByDegree ? 20 + Math.min(degree * 2, 25) : 25
      })
      .attr('dy', 5)
      .style('pointer-events', 'none')
      .style('text-shadow', '1px 1px 2px white, -1px -1px 2px white')
    : null

    // 边界内边距
    const padding = 30
    
    sim.on('tick', () => {
      // 限制节点在画布边界内
      nodes.forEach(d => {
        d.x = Math.max(padding, Math.min(width - padding, d.x))
        d.y = Math.max(padding, Math.min(height - padding, d.y))
      })
      
      link
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)

      if (linkLabel) {
        linkLabel
          .attr('x', (d) => (d.source.x + d.target.x) / 2)
          .attr('y', (d) => (d.source.y + d.target.y) / 2)
      }

      node.attr('cx', (d) => d.x).attr('cy', (d) => d.y)

      if (label) {
        label.attr('x', (d) => d.x).attr('y', (d) => d.y)
      }
    })

    function dragstarted(event, d) {
      if (!event.active) sim.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event, d) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event, d) {
      if (!event.active) sim.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    // 点击空白处不取消选择（保留当前选中状态）
    // svg.on('click', () => {
    //   setSelectedNodes([])
    //   setSelectedNodeInfo(null)
    //   setNodeDetails(null)
    // })
  }

  const handleNodeClick = (node) => {
    const isSelected = selectedNodes.includes(node.id)
    const newSelected = isSelected
      ? selectedNodes.filter(id => id !== node.id)
      : [...selectedNodes, node.id]
    setSelectedNodes(newSelected)
    setSelectedNodeInfo(node)
    loadNodeDetails(node)
  }

  const expandNode = async (node) => {
    try {
      message.loading('加载关联节点...', 0)
      let newData
      const nodeLabel = node.label || (node.labels && node.labels[0])
      
      if (nodeLabel === 'Herb' || (node.labels && node.labels.includes('Herb'))) {
        newData = await knowledgeGraphAPI.getHerbRelationships(
          node.name,
          1,
          50, // 限制返回50个关联节点，避免性能问题
          0, // skip为0
          pagination.relationshipTypes
        )
      } else if (nodeLabel === 'Medic' || (node.labels && node.labels.includes('Medic'))) {
        newData = await knowledgeGraphAPI.getMedicRelationships(
          node.name,
          1,
          50, // 限制返回50个关联节点，避免性能问题
          0, // skip为0
          pagination.relationshipTypes
        )
      } else {
        newData = await knowledgeGraphAPI.getPrescriptionRelationships(
          node.name,
          1,
          50, // 限制返回50个关联节点，避免性能问题
          0, // skip为0
          pagination.relationshipTypes
        )
      }
      
      // 合并数据
      const existingNodeIds = new Set(graphData.nodes.map(n => n.id))
      const existingLinkIds = new Set(graphData.links.map(l => {
        const sourceId = typeof l.source === 'object' ? l.source.id : l.source
        const targetId = typeof l.target === 'object' ? l.target.id : l.target
        return `${sourceId}-${targetId}`
      }))
      
      const newNodes = newData.nodes.filter(n => !existingNodeIds.has(n.id))
      const newLinks = newData.links.filter(l => {
        const sourceId = typeof l.source === 'object' ? l.source.id : l.source
        const targetId = typeof l.target === 'object' ? l.target.id : l.target
        const linkId = `${sourceId}-${targetId}`
        return !existingLinkIds.has(linkId)
      })
      
      // 规范化links，确保source和target都是字符串（节点ID）
      const normalizedLinks = [...graphData.links, ...newLinks].map(link => ({
        ...link,
        source: typeof link.source === 'object' ? link.source.id : link.source,
        target: typeof link.target === 'object' ? link.target.id : link.target
      }))

      const mergedData = {
        nodes: [...graphData.nodes, ...newNodes],
        links: normalizedLinks
      }
      
      setGraphData(mergedData)
      renderGraph(mergedData)
      message.destroy()
      message.success(`已展开 ${newNodes.length} 个关联节点`)
    } catch (error) {
      message.destroy()
      message.error('展开节点失败')
      console.error(error)
    }
  }

  const updatePagination = (newPagination) => {
    setPagination(newPagination)
  }

  const resetView = () => {
    // 重新加载全量图谱数据，实现真正的重置
    loadGraphData()
  }

  const clearGraph = () => {
    setGraphData({ nodes: [], links: [] })
    setSelectedNodes([])
    setSelectedNodeInfo(null)
    setNodeDetails(null)
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
  }

  const findSimilarNodes = async () => {
    if (!selectedNodeInfo) {
      message.warning('请先选择一个节点')
      return
    }

    try {
      setAnalyzing(true)
      // 根据节点类型调用不同的API
      let similarNodesList = [];

      if (selectedNodeInfo.label === 'Herb' || selectedNodeInfo.labels?.includes('Herb')) {
        const response = await knowledgeGraphAPI.findSimilarHerbs(selectedNodeInfo.name)
        console.log('相似药材API返回数据:', response)
        similarNodesList = response.similar_herbs || []
        console.log('相似药材列表:', similarNodesList)
      } else if (selectedNodeInfo.label === 'Prescription' || selectedNodeInfo.labels?.includes('Prescription')) {
        const response = await knowledgeGraphAPI.findSimilarPrescriptions(selectedNodeInfo.name)
        console.log('相似方剂API返回数据:', response)
        similarNodesList = response.similar_prescriptions || []
        console.log('相似方剂列表:', similarNodesList)
      } else if (selectedNodeInfo.label === 'Medic' || selectedNodeInfo.labels?.includes('Medic')) {
        const response = await knowledgeGraphAPI.findSimilarMedics(selectedNodeInfo.name)
        console.log('相似中成药API返回数据:', response)
        similarNodesList = response.similar_medics || []
        console.log('相似中成药列表:', similarNodesList)
      } else {
        message.warning('暂不支持该节点类型的相似节点查找')
        setSimilarNodes([])
        return
      }

      setSimilarNodes(similarNodesList)

      if (similarNodesList.length > 0) {
        message.success(`找到 ${similarNodesList.length} 个相似节点`)
      }
    } catch (error) {
      console.error('查找相似节点失败:', error)
      message.error('查找相似节点失败')
      setSimilarNodes([])
    } finally {
      setAnalyzing(false)
    }
  }

  const analyzeCurrentGraph = async () => {
    try {
      setAnalyzing(true)

      // 基于当前过滤条件获取实际显示的节点和连接
      let displayNodes = [...graphData.nodes]
      let displayLinks = [...graphData.links]

      // 应用节点类型过滤
      if (filterOptions.nodeType !== 'all') {
        displayNodes = displayNodes.filter(node => {
          const label = node.label || (node.labels && node.labels[0]) || ''
          return label === filterOptions.nodeType
        })
      }

      // 根据节点类型过滤links
      if (filterOptions.nodeType !== 'all') {
        const nodeIds = new Set(displayNodes.map(n => n.id))
        displayLinks = displayLinks.filter(link => {
          const sourceId = typeof link.source === 'object' ? link.source.id : link.source
          const targetId = typeof link.target === 'object' ? link.target.id : link.target
          return nodeIds.has(sourceId) && nodeIds.has(targetId)
        })
      }

      // 去重links（相同source和target的连接只保留一个）
      const originalLinkCount = displayLinks.length
      const linkSet = new Set()
      const duplicateCount = { before: originalLinkCount, after: 0 }
      displayLinks = displayLinks.filter(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        // 确保两个ID都存在且不为空
        if (!sourceId || !targetId) return false
        // 排除自连接
        if (sourceId === targetId) return false
        // 创建唯一键
        const linkKey = `${sourceId}-${targetId}`
        if (linkSet.has(linkKey)) return false
        linkSet.add(linkKey)
        return true
      })
      duplicateCount.after = displayLinks.length

      // 计算显示节点的度数（基于显示的连接）
      const nodeDegrees = {}
      displayNodes.forEach(node => {
        nodeDegrees[node.id] = 0
      })
      displayLinks.forEach(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source
        const targetId = typeof link.target === 'object' ? link.target.id : link.target
        if (nodeDegrees[sourceId] !== undefined) nodeDegrees[sourceId]++
        if (nodeDegrees[targetId] !== undefined) nodeDegrees[targetId]++
      })

      // 应用度数范围过滤（使用显示数据的度数）
      if (filterOptions.degreeRange && filterOptions.degreeRange.length === 2) {
        const [minDegree, maxDegree] = filterOptions.degreeRange
        const filteredNodeIds = displayNodes.filter(node => {
          const degree = nodeDegrees[node.id] || 0
          return degree >= minDegree && degree <= maxDegree
        }).map(n => n.id)

        displayNodes = displayNodes.filter(node => filteredNodeIds.includes(node.id))
        displayLinks = displayLinks.filter(link => {
          const sourceId = typeof link.source === 'object' ? link.source.id : link.source
          const targetId = typeof link.target === 'object' ? link.target.id : link.target
          return filteredNodeIds.includes(sourceId) && filteredNodeIds.includes(targetId)
        })

        // 重新计算过滤后的度数
        const filteredNodeDegrees = {}
        displayNodes.forEach(node => {
          filteredNodeDegrees[node.id] = 0
        })
        displayLinks.forEach(link => {
          const sourceId = typeof link.source === 'object' ? link.source.id : link.source
          const targetId = typeof link.target === 'object' ? link.target.id : link.target
          if (filteredNodeDegrees[sourceId] !== undefined) filteredNodeDegrees[sourceId]++
          if (filteredNodeDegrees[targetId] !== undefined) filteredNodeDegrees[targetId]++
        })
        // 更新度数为过滤后的值
        Object.assign(nodeDegrees, filteredNodeDegrees)
      }

      // 找出高度数节点（度数≥3）
      const highDegreeNodes = Object.entries(nodeDegrees)
        .filter(([_, degree]) => degree >= 3)
        .sort(([_, a], [__, b]) => b - a)
        .slice(0, 10)
        .map(([nodeId, degree]) => {
          const node = displayNodes.find(n => n.id === nodeId)
          return {
            name: node ? node.name : nodeId,
            degree: degree
          }
        })

      let analysisText = `图谱分析结果:\n\n`

      // 显示后台实际数据和当前显示数据
      analysisText += `【数据概览】\n`
      analysisText += `后台实际数据: ${graphData.nodes.length}个节点, ${graphData.links.length}条连接\n`
      analysisText += `当前显示数据: ${displayNodes.length}个节点, ${displayLinks.length}条连接`

      // 如果有去重，说明去重了多少
      if (duplicateCount.before !== duplicateCount.after) {
        const duplicatesRemoved = duplicateCount.before - duplicateCount.after
        analysisText += ` (已去重: 移除了${duplicatesRemoved}条重复连接)\n\n`
      } else {
        analysisText += `\n\n`
      }

      // 如果有过滤，说明过滤了多少
      const filteredNodes = graphData.nodes.length - displayNodes.length
      const filteredLinks = graphData.links.length - displayLinks.length
      if (filteredNodes > 0 || filteredLinks > 0) {
        analysisText += `已过滤: ${filteredNodes}个节点, ${filteredLinks}条连接\n\n`
      }

      // 显示节点类型分布（同时显示后台和当前显示）
      const allNodeTypeCounts = {}
      graphData.nodes.forEach(node => {
        const label = node.label || (node.labels && node.labels[0]) || 'Unknown'
        allNodeTypeCounts[label] = (allNodeTypeCounts[label] || 0) + 1
      })

      const displayNodeTypeCounts = {}
      displayNodes.forEach(node => {
        const label = node.label || (node.labels && node.labels[0]) || 'Unknown'
        displayNodeTypeCounts[label] = (displayNodeTypeCounts[label] || 0) + 1
      })

      analysisText += `【节点类型分布】\n`
      Object.entries(allNodeTypeCounts).forEach(([label, allCount]) => {
        const displayCount = displayNodeTypeCounts[label] || 0
        analysisText += `- ${NODE_LABELS_CN[label] || label}: 后台${allCount}个, 显示${displayCount}个\n`
      })

      analysisText += `\n高度数节点 (度数≥3): ${highDegreeNodes.length}个\n`
      highDegreeNodes.forEach(node => {
        analysisText += `- ${node.name}: ${node.degree}度\n`
      })

      // 显示关系类型统计（同时显示后台和当前显示）
      const allLinkTypeCounts = {}
      graphData.links.forEach(link => {
        const type = link.type || 'Unknown'
        allLinkTypeCounts[type] = (allLinkTypeCounts[type] || 0) + 1
      })

      const displayLinkTypeCounts = {}
      displayLinks.forEach(link => {
        const type = link.type || 'Unknown'
        displayLinkTypeCounts[type] = (displayLinkTypeCounts[type] || 0) + 1
      })

      analysisText += `\n【关系类型统计】\n`
      Object.entries(allLinkTypeCounts).forEach(([type, allCount]) => {
        const displayCount = displayLinkTypeCounts[type] || 0
        const typeLabel = RELATIONSHIP_LABELS_CN[type] || type
        analysisText += `- ${typeLabel}(${type}): 后台${allCount}条, 显示${displayCount}条\n`
      })

      // 如果有过滤条件，显示过滤信息
      if (filterOptions.nodeType !== 'all' || (filterOptions.degreeRange && filterOptions.degreeRange.length === 2)) {
        analysisText += `\n\n【当前过滤条件】\n`
        if (filterOptions.nodeType !== 'all') {
          analysisText += `- 节点类型: ${NODE_LABELS_CN[filterOptions.nodeType] || filterOptions.nodeType}\n`
        }
        if (filterOptions.degreeRange && filterOptions.degreeRange.length === 2) {
          analysisText += `- 度数范围: ${filterOptions.degreeRange[0]} - ${filterOptions.degreeRange[1]}\n`
        }
      }
      
      Modal.info({
        title: '当前图谱分析',
        width: 600,
        content: (
          <div style={{ fontSize: '14px', lineHeight: '1.8', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif' }}>
            <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontFamily: 'inherit' }}>
              {analysisText}
            </pre>
          </div>
        )
      })
      
      message.success('图谱分析完成')
    } catch (error) {
      console.error('图谱分析失败:', error)
      message.error('图谱分析失败')
    } finally {
      setAnalyzing(false)
    }
  }

  const tabItems = [
    {
      key: 'selectedNode',
      label: '选中节点信息',
      children: selectedNodeInfo ? (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <div style={{ flex: 1, overflow: 'auto' }}>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="名称">{selectedNodeInfo.name}</Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={NODE_COLORS[selectedNodeInfo.label || selectedNodeInfo.labels?.[0]]}>
                  {selectedNodeInfo.label || selectedNodeInfo.labels?.[0]}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
            
            {loadingDetails && (
              <div style={{ textAlign: 'center', padding: '10px' }}>
                <Spin size="small" /> 加载详情中...
              </div>
            )}
            
            {nodeDetails && !loadingDetails && (
              <div style={{ marginTop: 12 }}>
                {renderDetailsSmart(nodeDetails, selectedNodeInfo)}
              </div>
            )}
          </div>
          
          <Divider />
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
          <InfoCircleOutlined style={{ fontSize: 24, marginBottom: 8 }} />
          <p>请搜索或点击节点查看详细信息</p>
        </div>
      ),
    },
    {
      key: 'filters',
      label: '显示选项',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <h4>显示设置</h4>
            <div style={{ marginBottom: 8 }}>
              <span style={{ marginRight: 8 }}>显示节点标签:</span>
              <Switch checked={showLabels} onChange={setShowLabels} />
            </div>
            <div style={{ marginBottom: 8 }}>
              <span style={{ marginRight: 8 }}>显示关系标签:</span>
              <Switch checked={showLinkLabels} onChange={setShowLinkLabels} />
            </div>
            <div style={{ marginBottom: 8 }}>
              <span style={{ marginRight: 8 }}>按度数调整节点大小:</span>
              <Switch checked={nodeSizeByDegree} onChange={setNodeSizeByDegree} />
            </div>
          </div>
          
          <Divider />
          
          <div>
            <h4>节点类型过滤</h4>
            <Select
              style={{ width: '100%' }}
              value={filterOptions.nodeType}
              onChange={(value) => {
                setFilterOptions({ ...filterOptions, nodeType: value })
              }}
            >
              <Option value="all">全部</Option>
              {(() => {
                // 从实际数据中提取所有唯一的节点类型
                const uniqueLabels = Array.from(new Set(
                  graphData.nodes
                    .map(node => node.label || (node.labels && node.labels[0]) || '')
                    .filter(label => label) // 过滤掉空值
                ))
                return uniqueLabels.map(label => (
                  <Option key={label} value={label}>
                    {NODE_LABELS_CN[label] || label}
                  </Option>
                ))
              })()}
            </Select>
            <div style={{ marginTop: 8, color: '#666', fontSize: '12px' }}>
              {filterOptions.nodeType === 'all'
                ? `显示所有节点: ${graphData.nodes.length}`
                : `已筛选: ${graphData.nodes.filter(n => {
                    const label = n.label || (n.labels && n.labels[0]) || ''
                    return label === filterOptions.nodeType
                  }).length} 个节点`
              }
            </div>
          </div>

          <Divider />

          <div>
            <h4>度数范围过滤</h4>
            <div style={{ marginBottom: 8 }}>
              <Slider
                range
                min={0}
                max={(() => {
                  // 计算实际数据的最大度数
                  if (!graphData.nodes || graphData.nodes.length === 0) return 100
                  const nodeDegrees = {}
                  graphData.nodes.forEach(node => {
                    nodeDegrees[node.id] = 0
                  })
                  graphData.links.forEach(link => {
                    const sourceId = typeof link.source === 'object' ? link.source.id : link.source
                    const targetId = typeof link.target === 'object' ? link.target.id : link.target
                    if (nodeDegrees[sourceId] !== undefined) nodeDegrees[sourceId]++
                    if (nodeDegrees[targetId] !== undefined) nodeDegrees[targetId]++
                  })
                  const maxDegree = Math.max(...Object.values(nodeDegrees), 10)
                  return Math.max(maxDegree, 10)
                })()}
                value={filterOptions.degreeRange}
                onChange={(value) => {
                  setFilterOptions({ ...filterOptions, degreeRange: value })
                }}
              />
            </div>
            <div style={{ color: '#666', fontSize: '12px' }}>
              度数范围: {filterOptions.degreeRange[0]} - {filterOptions.degreeRange[1]}
            </div>
          </div>
        </Space>
      ),
    },
    {
      key: 'similarity',
      label: '相似节点推荐',
      children: (
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <h4>查找相似节点</h4>
            <p style={{ color: '#666', fontSize: '12px' }}>
              选中图谱中的一个节点，然后点击按钮查找与其相似的节点。<br/>
              • 药材：基于共享功效计算<br/>
              • 方剂/中成药：基于共享药材计算<br/>
            </p>
            <Button
              block
              type="primary"
              onClick={findSimilarNodes}
              loading={analyzing}
              disabled={!selectedNodeInfo}
            >
              查找相似节点
            </Button>
            {selectedNodeInfo ? (
              <div style={{ marginTop: 8, color: '#52c41a' }}>
                已选中: {selectedNodeInfo.name}
              </div>
            ) : (
              <div style={{ marginTop: 8, color: '#999' }}>
                请先点击选中一个节点
              </div>
            )}
          </div>

          <Divider />

          <div>
            <h4>图谱分析</h4>
            <Button
              block
              onClick={analyzeCurrentGraph}
              loading={analyzing}
            >
              分析当前图谱
            </Button>
            <p style={{ marginTop: 8, color: '#666', fontSize: '12px' }}>
              显示高度数节点和关系类型统计
            </p>
          </div>

          {similarNodes.length > 0 && (
            <>
              <Divider />
              <div>
                <h4>相似节点 ({similarNodes.length})</h4>
                <List
                  size="small"
                  dataSource={similarNodes.slice(0, 5)}
                  renderItem={(item, _) => {
                    // 安全地获取节点信息，支持不同类型的数据结构
                    // 药材: { herb: {...}, similarity: ... }
                    // 方剂: { prescription: {...}, similarity: ... }
                    // 中成药: { medic: {...}, similarity: ... }
                    const node = item.herb || item.prescription || item.medic || item.node || item
                    const label = node.label || (node.labels && node.labels[0]) || 'Herb'
                    const name = node.name || '未知节点'
                    const similarity = item.similarity !== undefined ? item.similarity : 0

                    // 根据相似度显示不同的颜色
                    let similarityColor = '#666'
                    if (similarity >= 0.7) {
                      similarityColor = '#52c41a' // 绿色
                    } else if (similarity >= 0.4) {
                      similarityColor = '#faad14' // 黄色
                    } else {
                      similarityColor = '#ff4d4f' // 红色
                    }

                    return (
                      <List.Item>
                        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                          <span>
                            <Tag color={NODE_COLORS[label] || '#1890ff'}>
                              {name}
                            </Tag>
                          </span>
                          <span style={{ color: similarityColor, fontWeight: 'bold' }}>
                            {(similarity * 100).toFixed(1)}%
                          </span>
                        </div>
                      </List.Item>
                    )
                  }}
                />
              </div>
            </>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: '20px' }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          {/* 选中节点信息显示区域 */}
          {selectedNodeInfo && (
            <Card 
              size="small" 
              style={{ 
                marginBottom: 12, 
                backgroundColor: '#ffffff',
                border: `2px solid ${NODE_COLORS[selectedNodeInfo.label || selectedNodeInfo.labels?.[0]] || NODE_COLORS.default}`
              }}
              title="当前选中节点"
            >
              <Row justify="space-between" align="middle">
                <Col>
                  <Space>
                    <Tag color={NODE_COLORS[selectedNodeInfo.label || selectedNodeInfo.labels?.[0]]}>
                      {selectedNodeInfo.label || selectedNodeInfo.labels?.[0]}
                    </Tag>
                    <span style={{ fontSize: 16, fontWeight: 'bold' }}>{selectedNodeInfo.name}</span>
                  </Space>
                </Col>
                <Col>
                  <Space>
                    <Button 
                      size="small" 
                      type="primary"
                      onClick={() => expandNode(selectedNodeInfo)}
                    >
                      展开关联节点
                    </Button>
                    <Button 
                      size="small" 
                      danger 
                      onClick={() => {
                        setSelectedNodes(selectedNodes.filter(id => id !== selectedNodeInfo.id))
                        setSelectedNodeInfo(null)
                        setNodeDetails(null)
                      }}
                    >
                      取消选择
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Card>
          )}
          
          <Card>
            <Space wrap style={{ marginBottom: 16 }}>
              <Input
                placeholder="输入药材、方剂或中成药名称"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onPressEnter={() => loadGraphData()}
                style={{ width: 250 }}
                prefix={<SearchOutlined />}
              />
              <Select
                value={searchType}
                onChange={(value) => setSearchType(value)}
                style={{ width: 120 }}
                options={[
                  { value: 'auto', label: '自动识别' },
                  { value: 'Herb', label: '药材' },
                  { value: 'Prescription', label: '方剂' },
                  { value: 'Medic', label: '中成药' }
                ]}
              />
              <Button type="primary" onClick={() => loadGraphData()} icon={<SearchOutlined />}>
                查询
              </Button>
              <Button onClick={resetView} icon={<ReloadOutlined />}>
                重置视图
              </Button>
              <Button 
                onClick={toggleFullscreen} 
                icon={isFullscreen ? <CompressOutlined /> : <ExpandOutlined />}
              >
                {isFullscreen ? '退出全屏' : '全屏'}
              </Button>
              <Button onClick={exportGraphImage} icon={<DownloadOutlined />}>
                导出图谱
              </Button>
              <Button
                onClick={showExportModal}
                icon={<DownloadOutlined />}
                disabled={selectedNodes.length === 0}
              >
                导出选中数据
              </Button>
            </Space>
            
            {/* 导出深度选择Modal */}
            <Modal
              title="导出子图设置"
              open={isExportModalVisible}
              onOk={handleExport}
              onCancel={() => setIsExportModalVisible(false)}
              okText="导出"
              cancelText="取消"
            >
              <div style={{ marginBottom: 16 }}>
                <p><strong>当前选中节点：{selectedNodeInfo ? selectedNodeInfo.name : '无'}</strong></p>
                <p style={{ color: '#666', fontSize: '12px' }}>将以该节点为中心导出子图</p>
                <p>导出深度：控制从选中节点向外扩展的层级</p>
              </div>
              <div>
                <span style={{ marginRight: 8 }}>深度：</span>
                <Select
                  value={exportDepth}
                  onChange={(value) => setExportDepth(value)}
                  style={{ width: 120 }}
                  options={[
                    { value: 1, label: '1层（直接关联）' },
                    { value: 2, label: '2层' },
                    { value: 3, label: '3层' },
                    { value: 4, label: '4层' },
                    { value: 5, label: '5层（全部）' }
                  ]}
                />
              </div>
              <div style={{ marginTop: 16, color: '#666', fontSize: '12px' }}>
                <p>深度说明：</p>
                <p>• 1层：只导出与选中节点直接相连的节点</p>
                <p>• 2层：包含直接关联和间接关联的节点</p>
                <p>• 以此类推...</p>
              </div>
            </Modal>
            
            <div style={{ color: '#666', fontSize: '12px', marginTop: 8 }}>
              示例：矮脚罗伞、甘草、桂枝汤、六味地黄丸（输入后按回车或点击查询）
            </div>
            
            <Row gutter={[8, 8]} style={{ marginTop: 16 }}>
              <Col>
                <span>显示最大节点数: </span>
              </Col>
              <Col>
                <Input
                  type="number"
                  min="10"
                  max="200"
                  value={pagination.limit}
                  onChange={(e) => {
                    const newLimit = parseInt(e.target.value) || 30
                    updatePagination({ ...pagination, skip: 0, limit: newLimit })
                  }}
                  style={{ width: 80 }}
                />
              </Col>
              <Col>
                <Button
                  type="primary"
                  size="small"
                  onClick={() => updatePagination({ ...pagination, skip: 0, limit: 30 })}
                >
                  重置为30
                </Button>
              </Col>
              <Col>
                <span style={{ color: '#666', fontSize: '12px' }}>
                  总节点数: {graphData.nodes.length}
                </span>
              </Col>
              <Col>
                <span style={{ color: '#666', fontSize: '12px' }}>
                  当前显示: {Math.min(pagination.skip + pagination.limit, graphData.nodes.length)}/{graphData.nodes.length}
                </span>
              </Col>
            </Row>
            <Row gutter={[8, 8]} style={{ marginTop: 8 }}>
              <Col>
                <span>筛选关系类型: </span>
              </Col>
              <Col>
                <Select
                  mode="multiple"
                  style={{ minWidth: 200 }}
                  placeholder="选择关系类型（可多选）"
                  value={pagination.relationshipTypes ? pagination.relationshipTypes.split(',') : []}
                  onChange={(selectedValues) => {
                    updatePagination({ 
                      ...pagination, 
                      relationshipTypes: selectedValues.length > 0 ? selectedValues.join(',') : null 
                    })
                  }}
                >
                  {STANDARD_RELATIONSHIP_TYPES.map(relType => (
                    <Option key={relType} value={relType}>
                      <span style={{ color: LINK_COLORS[relType] }}>●</span> {RELATIONSHIP_LABELS_CN[relType] || relType}
                    </Option>
                  ))}
                </Select>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={isFullscreen ? 24 : 18}>
          <Card 
            title="知识图谱可视化" 
            extra={
              <Space>
                <Tooltip title="双击节点展开关联">
                  <InfoCircleOutlined />
                </Tooltip>
                <span style={{ color: '#999', fontSize: 12 }}>
                  节点数: {graphData.nodes.length} | 关系数: {graphData.links.length}
                </span>
              </Space>
            }
            ref={containerRef}
          >
            {loading && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 600, flexDirection: 'column' }}>
                <Spin size="large" />
                <div style={{ marginTop: 16 }}>加载中...</div>
              </div>
            )}
            
            {graphData.nodes.length === 0 && !loading && (
              <Empty description="请输入关键词查询知识图谱" style={{ marginTop: 200 }} />
            )}
            <svg 
              ref={svgRef} 
              style={{ 
                width: '100%', 
                height: isFullscreen ? window.innerHeight - 300 : 600, 
                border: '1px solid #d9d9d9',
                backgroundColor: '#fafafa',
                display: loading || graphData.nodes.length === 0 ? 'none' : 'block'
              }} 
            />
            
            {/* 动态图例 - 只显示图谱中存在的节点类型 */}
            {!loading && graphData.nodes.length > 0 && (
              <div style={{ 
                marginTop: 16, 
                padding: '12px 16px',
                backgroundColor: '#f8f9fa',
                border: '1px solid #e8e8e8',
                borderRadius: '8px'
              }}>
                <div style={{ 
                  display: 'flex', 
                  flexWrap: 'wrap', 
                  alignItems: 'center',
                  gap: '12px',
                  marginBottom: '8px'
                }}>
                  <span style={{ fontWeight: 'bold', marginRight: '8px', whiteSpace: 'nowrap' }}>图例:</span>
                  {(() => {
                    // 从当前图谱数据中提取所有唯一的节点类型
                    const uniqueLabels = Array.from(new Set(
                      graphData.nodes
                        .map(node => node.label || (node.labels && node.labels[0]) || '')
                        .filter(label => label && label !== 'default')
                    ))
                    return uniqueLabels.map(label => {
                      const color = NODE_COLORS[label] || NODE_COLORS.default
                      const labelCN = NODE_LABELS_CN[label] || label
                      return (
                        <div key={label} style={{ 
                          display: 'flex', 
                          alignItems: 'center',
                          padding: '4px 8px',
                          backgroundColor: '#fff',
                          border: '1px solid #d9d9d9',
                          borderRadius: '4px',
                          whiteSpace: 'nowrap'
                        }}>
                          <span style={{
                            display: 'inline-block',
                            width: '12px',
                            height: '12px',
                            backgroundColor: color,
                            borderRadius: '50%',
                            marginRight: '6px'
                          }} />
                          <span>{labelCN}</span>
                        </div>
                      )
                    })
                  })()}
                </div>
                
              </div>
            )}
          </Card>
        </Col>

        {!isFullscreen && (
          <Col span={6}>
            <Card 
              title="控制面板" 
              style={{ 
                marginBottom: 16,
                height: isFullscreen ? 'calc(100vh - 200px)' : 785, // 调回785px
                display: 'flex',
                flexDirection: 'column'
              }}
              styles={{
                body: {
                  flex: 1,
                  overflow: 'hidden', // 隐藏外部滚动条
                  padding: 0
                }
              }}
            >
              <div style={{ 
                height: 785, // 调回785px
                overflow: 'auto', // 内部滚动条
                padding: '16px',
                display: 'flex',
                flexDirection: 'column'
              }}>
                <Tabs 
                  defaultActiveKey="selectedNode" 
                  onChange={(key) => setActiveTab(key)} 
                  items={tabItems}
                  style={{ flex: 1 }}  // 让 Tabs 占据剩余空间
                />
                
                {/* 操作提示固定在底部 */}
                <Divider />
                <div style={{ fontSize: '11px', color: '#666', padding: '8px 0' }}>
                  <p><strong>操作提示:</strong></p>
                  <p>• 双击节点可展开关联节点</p>
                  <p>• 点击节点查看详细信息</p>
                   <p>• 每个颜色代表一种节点类型</p>
                  <p>• 图例仅显示当前图谱中存在的节点类型</p>
                </div>
              </div>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  )
}

export default KnowledgeGraph