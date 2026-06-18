import React, { useEffect, useState } from 'react'
import { Table, Button, Space, Input, Modal, Form, message, Tag, Tooltip, Upload, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import api, { herbAPI } from '../services/api'

const { Option } = Select

// 截断文本函数
const truncateText = (text, maxLength = 50) => {
  if (!text) return '-'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const Herbs = () => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingRecord, setEditingRecord] = useState(null)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [form] = Form.useForm()
  const [isAdmin, setIsAdmin] = useState(false)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    pageSizeOptions: ['10', '15', '20', '50', '100']
  })
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchType, setSearchType] = useState('all')  // 搜索类型: all, name, function, nature

  // 检查用户角色
  useEffect(() => {
    const token = localStorage.getItem('token')
    const userStr = localStorage.getItem('user')
    if (!token) {
      message.warning('您还未登录，无法进行编辑操作')
    }
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        setIsAdmin(user.role === 'admin' || user.role === 'ADMIN')
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }
  }, [])

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60, fixed: 'left' },
    { title: '药材名称', dataIndex: 'name', key: 'name', width: 120, fixed: 'left' },
    { title: '拼音', dataIndex: 'pinyin', key: 'pinyin', width: 120 },
    { title: '英文名', dataIndex: 'english_name', key: 'english_name', width: 120, render: (text) => truncateText(text, 20) },
    { title: '别名', dataIndex: 'aliases', key: 'aliases', width: 150, render: (text) => truncateText(text, 30) },
    { title: '性味', dataIndex: 'nature', key: 'nature', width: 100 },
    { title: '归经', dataIndex: 'meridians', key: 'meridians', width: 120 },
    { 
      title: '功能主治', 
      dataIndex: 'function', 
      key: 'function', 
      width: 200,
      render: (text) => (
        <Tooltip title={text}>
          <span>{truncateText(text, 40)}</span>
        </Tooltip>
      )
    },
    { 
      title: '用法用量', 
      dataIndex: 'usage', 
      key: 'usage', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '药材基源', 
      dataIndex: 'source', 
      key: 'source', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '生境分布', 
      dataIndex: 'habitat', 
      key: 'habitat', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '原形态', 
      dataIndex: 'original_morphology', 
      key: 'original_morphology', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '性状', 
      dataIndex: 'properties', 
      key: 'properties', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '化学成分', 
      dataIndex: 'chemical_composition', 
      key: 'chemical_composition', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '各家论述', 
      dataIndex: 'discussions', 
      key: 'discussions', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '摘录', 
      dataIndex: 'excerpt', 
      key: 'excerpt', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '采收和储藏', 
      dataIndex: 'harvest_storage', 
      key: 'harvest_storage', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '炮制', 
      dataIndex: 'processing', 
      key: 'processing', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '临床应用', 
      dataIndex: 'clinical_application', 
      key: 'clinical_application', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '贮藏', 
      dataIndex: 'storage', 
      key: 'storage', 
      width: 100,
      render: (text) => truncateText(text, 20)
    },
    { 
      title: '鉴别', 
      dataIndex: 'identification', 
      key: 'identification', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '药理作用', 
      dataIndex: 'pharmacological_effects', 
      key: 'pharmacological_effects', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    { 
      title: '出处', 
      dataIndex: 'source_text', 
      key: 'source_text', 
      width: 150,
      render: (text) => truncateText(text, 30)
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
        <Space>
          {isAdmin ? (
            <>
              <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
                编辑
              </Button>
              <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)}>
                删除
              </Button>
            </>
          ) : (
            <Button type="link" icon={<EyeOutlined />} onClick={() => handleView(record)}>
              查看
            </Button>
          )}
        </Space>
      ),
    },
  ]

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async (keyword = '', nature = '', paginationParams = {}, type = searchType) => {
    try {
      setLoading(true)
      const { current = 1, pageSize = 10 } = paginationParams
      const skip = (current - 1) * pageSize
      
      if (keyword || nature) {
        const result = await herbAPI.searchHerbs(keyword, nature, type, skip, pageSize)
        setData(result.items || [])
        if (result.total !== undefined) {
          setPagination(prev => ({
            ...prev,
            total: result.total,
            current,
            pageSize
          }))
        }
      } else {
        const result = await herbAPI.getHerbs({ skip, limit: pageSize })
        setData(result.items || [])
        if (result.total !== undefined) {
          setPagination(prev => ({
            ...prev,
            total: result.total,
            current,
            pageSize
          }))
        }
      }
    } catch (error) {
      message.error('加载数据失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleTableChange = (newPagination, filters, sorter) => {
    loadData(searchKeyword, '', newPagination, searchType)
  }

  const handleSearch = (value) => {
    const trimmedValue = value.trim()
    setSearchKeyword(trimmedValue)
    loadData(trimmedValue, '', { current: 1, pageSize: pagination.pageSize }, searchType)
  }

  const handleSearchTypeChange = (value) => {
    setSearchType(value)
    if (searchKeyword) {
      loadData(searchKeyword, '', { current: 1, pageSize: pagination.pageSize }, value)
    }
  }

  const [viewModalVisible, setViewModalVisible] = useState(false)
  const [viewingRecord, setViewingRecord] = useState(null)

  const handleAdd = () => {
    setEditingRecord(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleView = (record) => {
    setViewingRecord(record)
    setViewModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingRecord(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleDelete = async (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条记录吗？',
      onOk: async () => {
        console.log('开始删除药材 ID:', id)
        console.log('当前token:', localStorage.getItem('token'))
        
        try {
          const response = await herbAPI.deleteHerb(id)
          console.log('删除响应:', response)
          message.success('删除成功')
          loadData()
        } catch (error) {
          console.error('删除失败详细信息:', error)
          console.error('错误状态码:', error.response?.status)
          console.error('错误信息:', error.response?.data)
          
          // 检查是否为401错误
          if (error.response?.status === 401) {
            message.error('未授权，请重新登录')
            // 不自动跳转，让用户手动重新登录
          } else if (error.response?.status === 403) {
            message.error('权限不足，需要管理员权限')
          } else {
            message.error(error.response?.data?.detail || '删除失败')
          }
        }
      },
    })
  }

  const handleSubmit = async () => {
    try {
      setSubmitLoading(true)
      const values = await form.validateFields()

      // 调试信息
      console.log('='.repeat(50))
      console.log('开始提交数据')
      console.log('编辑模式:', editingRecord ? '编辑' : '新增')
      console.log('药材ID:', editingRecord?.id)
      console.log('提交数据:', values)
      console.log('当前token:', localStorage.getItem('token'))
      console.log('Authorization头:', api.defaults.headers.common['Authorization'])
      console.log('='.repeat(50))

      if (editingRecord) {
        console.log('发送更新请求...')
        await herbAPI.updateHerb(editingRecord.id, values)
        console.log('更新成功')
        message.success('更新成功')
      } else {
        await herbAPI.createHerb(values)
        message.success('创建成功')
      }
      setModalVisible(false)
      loadData()
    } catch (error) {
      console.error('='.repeat(50))
      console.error('操作失败详细信息:')
      console.error('错误对象:', error)
      console.error('状态码:', error.response?.status)
      console.error('响应数据:', error.response?.data)
      console.error('请求配置:', error.config?.url, error.config?.method)
      console.error('='.repeat(50))

      // 显示错误消息但不自动跳转
      if (error.response?.status === 401) {
        message.error('未授权（401）- 请检查登录状态')
      } else if (error.response?.status === 403) {
        message.error('权限不足（403）- 需要管理员权限')
      } else {
        message.error(error.response?.data?.detail || '操作失败，请重试')
      }
    } finally {
      setSubmitLoading(false)
    }
  }

  // 导出示例数据（CSV格式）
  const exportSampleData = () => {
    const sampleData = [
      {
        name: '人参',
        pinyin: 'Ren Shen',
        english_name: 'Ginseng',
        aliases: '棒槌、神草、地精',
        nature: '甘、微苦，微温',
        meridians: '脾、肺、心、肾',
        function: '大补元气，复脉固脱，补脾益肺，生津养血，安神益智',
        usage: '3～9g，另煎兑服',
        source: '本品为五加科植物人参Panax ginseng C.A.Mey.的干燥根和根茎',
        source_text: '《中国药典》2020年版',
        habitat: '生于海拔数百米的针叶林或针阔混交林中',
        original_morphology: '多年生草本，主根粗壮，肉质',
        properties: '主根呈纺锤形或圆柱形',
        chemical_composition: '含人参皂苷、人参多糖、挥发油等',
        discussions: '《本草纲目》载：人参，气味甘，微寒，无毒',
        excerpt: '主治一切气血津液不足之证',
        harvest_storage: '秋季采挖，洗净后晒干或烘干',
        processing: '生晒参、红参、糖参等',
        clinical_application: '体虚欲脱、肢冷脉微、气短喘促',
        storage: '置阴凉干燥处，防蛀',
        identification: '显微鉴别、理化鉴别',
        pharmacological_effects: '增强免疫力、抗疲劳、调节血压',
        link: 'https://www.zysj.com.cn/zhongyaocai/renshen/index.html'
      }
    ]

    const headers = [
      'name', 'pinyin', 'english_name', 'aliases', 'nature', 'meridians',
      'function', 'usage', 'source', 'source_text', 'habitat',
      'original_morphology', 'properties', 'chemical_composition',
      'discussions', 'excerpt', 'harvest_storage', 'processing',
      'clinical_application', 'storage', 'identification',
      'pharmacological_effects', 'link'
    ]

    const headerNames = [
      '药材名称', '拼音', '英文名', '别名', '性味', '归经',
      '功能主治', '用法用量', '药材基源', '出处', '生境分布',
      '原形态', '性状', '化学成分', '各家论述', '摘录',
      '采收和储藏', '炮制', '临床应用', '贮藏', '鉴别',
      '药理作用', '数据来源链接'
    ]

    // 生成CSV内容
    let csvContent = '\uFEFF' // BOM for Excel
    csvContent += headerNames.join(',') + '\n'

    sampleData.forEach(item => {
      const row = headers.map(header => {
        let value = item[header] || ''
        // 处理包含逗号或换行符的值
        if (value.includes(',') || value.includes('\n') || value.includes('"')) {
          value = '"' + value.replace(/"/g, '""') + '"'
        }
        return value
      })
      csvContent += row.join(',') + '\n'
    })

    // 下载文件
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'herb_sample_data.csv'
    a.click()
    URL.revokeObjectURL(url)

    message.success('示例数据已导出')
  }

  // 导出所有数据
  const handleExportAll = async (format = 'csv') => {
    try {
      const response = await herbAPI.exportAll(format)
      // 创建Blob对象
      const blob = new Blob([response], { type: format === 'csv' ? 'text/csv' : 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `herbs_export.${format}`
      a.click()
      URL.revokeObjectURL(url)
      message.success(`导出成功，文件已下载`)
    } catch (error) {
      console.error('导出失败:', error)
      message.error('导出失败：' + (error.response?.data?.detail || error.message))
    }
  }

  // 批量导入
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)

  const handleImport = async () => {
    if (!importFile) {
      message.error('请选择要导入的CSV文件')
      return
    }

    try {
      setImporting(true)

      // 读取CSV文件
      const reader = new FileReader()
      reader.onload = async (e) => {
        try {
          const text = e.target.result
          const lines = text.split('\n')

          // 检查文件是否为空或格式错误
          if (lines.length < 2) {
            message.error('CSV文件格式错误：文件为空或只有表头')
            setImporting(false)
            return
          }

          // 检查第一行（表头）
          const firstLine = lines[0]

          // 检测是否使用中文逗号
          const useChineseComma = firstLine.includes('，')
          const comma = useChineseComma ? '，' : ','

          // 解析表头
          const rawHeaders = firstLine.split(comma).map(h => h.trim().replace(/^["']|["']$/g, ''))

          // 1. 检查是否有乱码（包含大量问号或不可见字符）
          const hasCorruptedHeaders = rawHeaders.some(h => /[?]{2,}/.test(h) || /[\uFFFD]/.test(h))
          if (hasCorruptedHeaders) {
            console.error('CSV文件编码错误，第一行内容:', firstLine)
            console.error('解析后的表头:', rawHeaders)
            message.error('CSV文件编码错误')
            setImporting(false)
            return
          }

          // 2. 检查字段是否匹配
          const expectedHeaders = ['药材名称', '拼音', '英文名', '别名', '性味', '归经',
            '功能主治', '用法用量', '药材基源', '出处', '生境分布',
            '原形态', '性状', '化学成分', '各家论述', '摘录',
            '采收和储藏', '炮制', '临床应用', '贮藏', '鉴别',
            '药理作用', '数据来源链接']

          // 中文表头到英文字段名的映射
          const headerMap = {
            '药材名称': 'name',
            '拼音': 'pinyin',
            '英文名': 'english_name',
            '别名': 'aliases',
            '性味': 'nature',
            '归经': 'meridians',
            '功能主治': 'function',
            '用法用量': 'usage',
            '药材基源': 'source',
            '出处': 'source_text',
            '生境分布': 'habitat',
            '原形态': 'original_morphology',
            '性状': 'properties',
            '化学成分': 'chemical_composition',
            '各家论述': 'discussions',
            '摘录': 'excerpt',
            '采收和储藏': 'harvest_storage',
            '炮制': 'processing',
            '临床应用': 'clinical_application',
            '贮藏': 'storage',
            '鉴别': 'identification',
            '药理作用': 'pharmacological_effects',
            '数据来源链接': 'link'
          }

          // 检查必需字段是否存在
          const missingFields = expectedHeaders.filter(h => !rawHeaders.includes(h))
          if (missingFields.length > 0) {
            message.error('字段不匹配')
            setImporting(false)
            return
          }

          const records = []
          for (let i = 1; i < lines.length; i++) {
            if (!lines[i].trim()) continue

            // 使用正确的分隔符解析
            const values = parseCSVLine(lines[i], comma)
            const record = {}
            rawHeaders.forEach((header, index) => {
              const englishField = headerMap[header] || header
              record[englishField] = values[index] || ''
            })
            records.push(record)
          }



  // 批量导入数据
          const result = await herbAPI.bulkImport(records)

          setImportModalVisible(false)
          setImportFile(null)
          loadData()

          const { created_count, failed_count } = result.data || {}
          if (failed_count > 0) {
            // 3. 其他所有错误都显示为"数据重复"
            message.error(`导入失败：数据重复`)
          } else {
            message.success(`导入成功：共${created_count}条记录`)
          }
        } catch (importError) {
          console.error('导入错误:', importError)

          // 检查是否是重复数据错误
          if (importError.response && importError.response.data) {
            const errorDetail = importError.response.data.detail || importError.response.data.message || ''
            if (errorDetail.includes('Duplicate') || errorDetail.includes('1062')) {
              message.error('导入失败：数据重复')
            } else {
              message.error('导入失败：' + (errorDetail || '未知错误'))
            }
          } else {
            message.error('导入失败：' + (importError.message || '未知错误'))
          }
          setImporting(false)
        }
      }

      reader.readAsText(importFile, 'UTF-8')
    } catch (error) {
      console.error('导入失败:', error)
      message.error('导入失败：' + (error.message || '未知错误'))
    } finally {
      setImporting(false)
    }
  }

  // 解析CSV行，处理带引号的字段
  const parseCSVLine = (line, delimiter = ',') => {
    const result = []
    let current = ''
    let inQuotes = false

    for (let i = 0; i < line.length; i++) {
      const char = line[i]

      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"'
          i++
        } else {
          inQuotes = !inQuotes
        }
      } else if (char === delimiter && !inQuotes) {
        result.push(current)
        current = ''
      } else {
        current += char
      }
    }
    result.push(current)
    return result
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          value={searchType}
          style={{ width: 120 }}
          onChange={handleSearchTypeChange}
          placeholder="搜索范围"
        >
          <Option value="all">全部</Option>
          <Option value="name">名称/别名</Option>
          <Option value="function">功能主治</Option>
          <Option value="nature">性味</Option>
        </Select>
        <Input.Search
          placeholder="搜索药材..."
          style={{ width: 280 }}
          onSearch={handleSearch}
          allowClear
        />
        <Button icon={<DownloadOutlined />} onClick={exportSampleData}>
          导出示例数据
        </Button>
        {isAdmin && (
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
              新增药材
            </Button>
            <Button icon={<UploadOutlined />} onClick={() => setImportModalVisible(true)}>
              批量导入
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => handleExportAll('csv')}>
              导出所有数据
            </Button>
          </>
        )}
      </Space>
      <Table
        loading={loading}
        columns={columns}
        dataSource={data}
        rowKey="id"
        scroll={{ x: 1500 }}
        pagination={pagination}
        onChange={handleTableChange}
      />
      {/* 查看详情模态框 */}
      <Modal
        title="药材详情"
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        footer={null}
        width={800}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
      >
        {viewingRecord && (
          <div style={{ lineHeight: 2 }}>
            <p><strong>ID:</strong> {viewingRecord.id}</p>
            <p><strong>药材名称:</strong> {viewingRecord.name}</p>
            <p><strong>拼音:</strong> {viewingRecord.pinyin || '-'}</p>
            <p><strong>英文名:</strong> {viewingRecord.english_name || '-'}</p>
            <p><strong>别名:</strong> {viewingRecord.aliases || '-'}</p>
            <p><strong>性味:</strong> {viewingRecord.nature || '-'}</p>
            <p><strong>归经:</strong> {viewingRecord.meridians || '-'}</p>
            <p><strong>功能主治:</strong> {viewingRecord.function || '-'}</p>
            <p><strong>用法用量:</strong> {viewingRecord.usage || '-'}</p>
            <p><strong>药材基源:</strong> {viewingRecord.source || '-'}</p>
            <p><strong>生境分布:</strong> {viewingRecord.habitat || '-'}</p>
            <p><strong>原形态:</strong> {viewingRecord.original_morphology || '-'}</p>
            <p><strong>性状:</strong> {viewingRecord.properties || '-'}</p>
            <p><strong>化学成分:</strong> {viewingRecord.chemical_composition || '-'}</p>
            <p><strong>各家论述:</strong> {viewingRecord.discussions || '-'}</p>
            <p><strong>摘录:</strong> {viewingRecord.excerpt || '-'}</p>
            <p><strong>采收和储藏:</strong> {viewingRecord.harvest_storage || '-'}</p>
            <p><strong>炮制:</strong> {viewingRecord.processing || '-'}</p>
            <p><strong>临床应用:</strong> {viewingRecord.clinical_application || '-'}</p>
            <p><strong>贮藏:</strong> {viewingRecord.storage || '-'}</p>
            <p><strong>鉴别:</strong> {viewingRecord.identification || '-'}</p>
            <p><strong>药理作用:</strong> {viewingRecord.pharmacological_effects || '-'}</p>
            <p><strong>出处:</strong> {viewingRecord.source_text || '-'}</p>
            <p><strong>数据来源链接:</strong> {viewingRecord.link || '-'}</p>
          </div>
        )}
      </Modal>

      {/* 编辑/新增模态框 */}
      <Modal
        title={editingRecord ? '编辑药材' : '新增药材'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        confirmLoading={submitLoading}
        width={900}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
        okText="确定"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="药材名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="pinyin" label="拼音">
            <Input />
          </Form.Item>
          <Form.Item name="english_name" label="英文名">
            <Input />
          </Form.Item>
          <Form.Item name="aliases" label="别名">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="nature" label="性味">
            <Input />
          </Form.Item>
          <Form.Item name="meridians" label="归经">
            <Input />
          </Form.Item>
          <Form.Item name="function" label="功能主治">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="usage" label="用法用量">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="source" label="药材基源">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="source_text" label="出处">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="habitat" label="生境分布">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="original_morphology" label="原形态">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="properties" label="性状">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="chemical_composition" label="化学成分">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="discussions" label="各家论述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="excerpt" label="摘录">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="harvest_storage" label="采收和储藏">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="processing" label="炮制">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="clinical_application" label="临床应用">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="storage" label="贮藏">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="identification" label="鉴别">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="pharmacological_effects" label="药理作用">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="link" label="数据来源链接">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量导入Modal */}
      <Modal
        title="批量导入药材数据"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={() => {
          setImportModalVisible(false)
          setImportFile(null)
        }}
        confirmLoading={importing}
        okText="开始导入"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <p><strong>请按照以下步骤操作：</strong></p>
          <ol style={{ marginLeft: 20, lineHeight: 2 }}>
            <li>点击"导出示例数据"下载CSV模板</li>
            <li>按照模板格式在CSV文件中填写数据</li>
            <li>选择填写好的CSV文件并点击"开始导入"</li>
          </ol>
        </div>
        <Upload
          beforeUpload={(file) => {
            if (!file.name.endsWith('.csv')) {
              message.error('请上传CSV格式文件')
              return Upload.LIST_IGNORE
            }
            setImportFile(file)
            return false
          }}
          onRemove={() => setImportFile(null)}
          maxCount={1}
        >
          <Button icon={<UploadOutlined />}>选择CSV文件</Button>
        </Upload>
        {importFile && (
          <div style={{ marginTop: 8, color: '#52c41a' }}>
            已选择: {importFile.name}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default Herbs