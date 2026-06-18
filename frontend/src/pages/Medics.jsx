import React, { useEffect, useState } from 'react'
import { Table, Button, Space, Input, Modal, Form, message, Select, Row, Col, Tooltip, Upload } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { medicAPI } from '../services/api'

const { TextArea } = Input
const { Option } = Select

// 截断文本函数
const truncateText = (text, maxLength = 50) => {
  if (!text) return '-'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const Medics = () => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState([])
  const [modalVisible, setModalVisible] = useState(false)
  const [viewModalVisible, setViewModalVisible] = useState(false)
  const [editingRecord, setEditingRecord] = useState(null)
  const [viewingRecord, setViewingRecord] = useState(null)
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
  const [searchType, setSearchType] = useState('all')  // 搜索类型: all, name, composition, function

  // 检查用户角色
  useEffect(() => {
    const userStr = localStorage.getItem('user')
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
    { title: '中文名称', dataIndex: 'name', key: 'name', width: 150, fixed: 'left' },
    { title: '英文名称', dataIndex: 'english_name', key: 'english_name', width: 120, render: (text) => truncateText(text, 20) },
    { title: '科室类别', dataIndex: 'category', key: 'category', width: 100 },
    { title: '大类', dataIndex: 'main_category', key: 'main_category', width: 100 },
    { title: '小类', dataIndex: 'sub_category', key: 'sub_category', width: 100 },
    { 
      title: '功能主治', 
      dataIndex: 'function_indication', 
      key: 'function_indication', 
      width: 200,
      render: (text) => (
        <Tooltip title={text}>
          <span>{truncateText(text, 35)}</span>
        </Tooltip>
      )
    },
    { 
      title: '药物组成', 
      dataIndex: 'composition', 
      key: 'composition', 
      width: 200,
      render: (text) => truncateText(text, 35)
    },
    { 
      title: '规格', 
      dataIndex: 'specification', 
      key: 'specification', 
      width: 120,
      render: (text) => truncateText(text, 20)
    },
    { 
      title: '用法用量', 
      dataIndex: 'usage_dosage', 
      key: 'usage_dosage', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '方解', 
      dataIndex: 'analysis', 
      key: 'analysis', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '临床应用', 
      dataIndex: 'clinical_application', 
      key: 'clinical_application', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '不良反应', 
      dataIndex: 'side_effects', 
      key: 'side_effects', 
      width: 120,
      render: (text) => truncateText(text, 20)
    },
    { 
      title: '禁忌', 
      dataIndex: 'contraindications', 
      key: 'contraindications', 
      width: 120,
      render: (text) => truncateText(text, 20)
    },
    { 
      title: '注意事项', 
      dataIndex: 'precautions', 
      key: 'precautions', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '药理毒理', 
      dataIndex: 'pharmacology', 
      key: 'pharmacology', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '君臣佐使', 
      dataIndex: 'monarch_ministers_assistants_couriers', 
      key: 'monarch_ministers_assistants_couriers', 
      width: 150,
      render: (text) => truncateText(text, 25)
    },
    { 
      title: '参考文献', 
      dataIndex: 'references', 
      key: 'references', 
      width: 120,
      render: (text) => truncateText(text, 20)
    },
    { 
      title: '数据来源', 
      dataIndex: 'source', 
      key: 'source', 
      width: 120,
      render: (text) => truncateText(text, 20)
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

  const loadData = async (keyword = '', paginationParams = {}, type = searchType) => {
    try {
      setLoading(true)
      const { current = 1, pageSize = 10 } = paginationParams
      const skip = (current - 1) * pageSize
      
      if (keyword) {
        const result = await medicAPI.searchMedics({ keyword, search_type: type, skip, limit: pageSize })
        setData(result.items || result || [])
        if (result.total !== undefined) {
          setPagination(prev => ({
            ...prev,
            total: result.total,
            current,
            pageSize
          }))
        }
      } else {
        const result = await medicAPI.getMedics({ skip, limit: pageSize })
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
    loadData(searchKeyword, newPagination, searchType)
  }

  const handleSearch = (value) => {
    const trimmedValue = value.trim()
    setSearchKeyword(trimmedValue)
    loadData(trimmedValue, { current: 1, pageSize: pagination.pageSize }, searchType)
  }

  const handleSearchTypeChange = (value) => {
    setSearchType(value)
    if (searchKeyword) {
      loadData(searchKeyword, { current: 1, pageSize: pagination.pageSize }, value)
    }
  }

  const handleAdd = () => {
    setEditingRecord(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setEditingRecord(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleView = (record) => {
    setViewingRecord(record)
    setViewModalVisible(true)
  }

  const handleDelete = async (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条记录吗？',
      onOk: async () => {
        try {
          await medicAPI.deleteMedic(id)
          message.success('删除成功')
          loadData()
        } catch (error) {
          message.error('删除失败')
          console.error(error)
        }
      },
    })
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingRecord) {
        await medicAPI.updateMedic(editingRecord.id, values)
        message.success('更新成功')
      } else {
        await medicAPI.createMedic(values)
        message.success('创建成功')
      }
      setModalVisible(false)
      loadData()
    } catch (error) {
      message.error('操作失败')
      console.error(error)
    }
  }

  // 导出示例数据（CSV格式）
  const exportSampleData = () => {
    const sampleData = [
      {
        name: '表实感冒颗粒',
        english_name: 'Biaoshi Ganmao Keli',
        category: '内科类',
        main_category: '一、解表剂',
        sub_category: '（一）辛温解表',
        composition: '麻黄、桂枝、防风、白芷、紫苏叶、葛根、生姜、陈皮、桔梗、苦杏仁（炒）、甘草',
        function_indication: '发汗解表，祛风散寒。用于感冒风寒表实证，症见恶寒重、发热轻、无汗、头项强痛、鼻流清涕、咳嗽、痰白稀',
        analysis: '方中麻黄性味辛苦温，发汗解表以散风寒，宣利肺气以平咳喘。桂枝性味辛甘温，解肌发表，温经散寒。两味同为君药',
        clinical_application: '感冒 因外感风寒，卫阳被郁所致，症见恶寒重，发热轻，无汗，头项强痛、鼻流清涕，咳嗽，痰白稀，舌质淡，苔薄白，脉浮紧',
        usage_dosage: '口服。一次 10～20g，一日 2～3 次。小儿酌减',
        specification: '每袋装 10g',
        side_effects: '目前尚未检索到不良反应报道',
        contraindications: '运动员禁用',
        precautions: '1.风热感冒及寒郁化热明显者慎用。 2.服药期间忌食辛辣、油腻。可食热粥以助汗出',
        pharmacology: '',
        monarch_ministers_assistants_couriers: '君药：麻黄、桂枝。臣药：防风、白芷、紫苏叶。佐药：葛根、生姜、陈皮、桔梗、苦杏仁。使药：甘草',
        references: '',
        source: '中国药典'
      }
    ]

    const headers = [
      'name', 'english_name', 'category', 'main_category', 'sub_category',
      'composition', 'function_indication', 'analysis', 'clinical_application',
      'usage_dosage', 'specification', 'side_effects', 'contraindications',
      'precautions', 'pharmacology', 'monarch_ministers_assistants_couriers',
      'references', 'source'
    ]

    const headerNames = [
      '中文名称', '英文名称', '科室类别', '大类', '小类',
      '药物组成', '功能主治', '方解', '临床应用',
      '用法用量', '规格', '不良反应', '禁忌',
      '注意事项', '药理毒理', '君臣佐使',
      '参考文献', '数据来源'
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
    a.download = 'medic_sample_data.csv'
    a.click()
    URL.revokeObjectURL(url)

    message.success('示例数据已导出')
  }

  // 导出所有数据
  const handleExportAll = async (format = 'csv') => {
    try {
      const response = await medicAPI.exportAll(format)
      // 创建Blob对象
      const blob = new Blob([response], { type: format === 'csv' ? 'text/csv' : 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `medics_export.${format}`
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
          const expectedHeaders = ['中文名称', '英文名称', '科室类别', '大类', '小类',
            '药物组成', '功能主治', '方解', '临床应用', '用法用量', '规格',
            '不良反应', '禁忌', '注意事项', '药理毒理', '君臣佐使', '参考文献', '数据来源']

          // 中文表头到英文字段名的映射
          const headerMap = {
            '中文名称': 'name',
            '英文名称': 'english_name',
            '科室类别': 'category',
            '大类': 'main_category',
            '小类': 'sub_category',
            '药物组成': 'composition',
            '功能主治': 'function_indication',
            '方解': 'analysis',
            '临床应用': 'clinical_application',
            '用法用量': 'usage_dosage',
            '规格': 'specification',
            '不良反应': 'side_effects',
            '禁忌': 'contraindications',
            '注意事项': 'precautions',
            '药理毒理': 'pharmacology',
            '君臣佐使': 'monarch_ministers_assistants_couriers',
            '参考文献': 'references',
            '数据来源': 'source'
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
          const result = await medicAPI.bulkImport(records)

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
          <Option value="name">名称</Option>
          <Option value="composition">组成</Option>
          <Option value="function">功能主治</Option>
        </Select>
        <Input.Search
          placeholder="搜索中成药..."
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
              新增中成药
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

      {/* 查看详情模态框 */}
      <Modal
        title="中成药详情"
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        footer={null}
        width={900}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
      >
        {viewingRecord && (
          <div style={{ lineHeight: 2 }}>
            <p><strong>ID:</strong> {viewingRecord.id}</p>
            <p><strong>中文名称:</strong> {viewingRecord.name}</p>
            <p><strong>英文名称:</strong> {viewingRecord.english_name || '-'}</p>
            <p><strong>科室类别:</strong> {viewingRecord.category || '-'}</p>
            <p><strong>大类:</strong> {viewingRecord.main_category || '-'}</p>
            <p><strong>小类:</strong> {viewingRecord.sub_category || '-'}</p>
            <p><strong>药物组成:</strong> {viewingRecord.composition || '-'}</p>
            <p><strong>功能主治:</strong> {viewingRecord.function_indication || '-'}</p>
            <p><strong>方解:</strong> {viewingRecord.analysis || '-'}</p>
            <p><strong>临床应用:</strong> {viewingRecord.clinical_application || '-'}</p>
            <p><strong>用法用量:</strong> {viewingRecord.usage_dosage || '-'}</p>
            <p><strong>规格:</strong> {viewingRecord.specification || '-'}</p>
            <p><strong>不良反应:</strong> {viewingRecord.side_effects || '-'}</p>
            <p><strong>禁忌:</strong> {viewingRecord.contraindications || '-'}</p>
            <p><strong>注意事项:</strong> {viewingRecord.precautions || '-'}</p>
            <p><strong>药理毒理:</strong> {viewingRecord.pharmacology || '-'}</p>
            <p><strong>君臣佐使:</strong> {viewingRecord.monarch_ministers_assistants_couriers || '-'}</p>
            <p><strong>参考文献:</strong> {viewingRecord.references || '-'}</p>
            <p><strong>数据来源:</strong> {viewingRecord.source || '-'}</p>
          </div>
        )}
      </Modal>

      <Table
        loading={loading}
        columns={columns}
        dataSource={data}
        rowKey="id"
        scroll={{ x: 2000 }}
        pagination={pagination}
        onChange={handleTableChange}
      />
      <Modal
        title={editingRecord ? '编辑中成药' : '新增中成药'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={900}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="中文名称" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="english_name" label="英文名称">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="category" label="科室类别">
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="main_category" label="大类">
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="sub_category" label="小类">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="composition" label="药物组成">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="function_indication" label="功能与主治">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="analysis" label="方解">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="clinical_application" label="临床应用">
            <TextArea rows={2} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="side_effects" label="不良反应">
                <TextArea rows={2} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contraindications" label="禁忌">
                <TextArea rows={2} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="precautions" label="注意事项">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="usage_dosage" label="用法与用量">
            <TextArea rows={2} />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="specification" label="规格">
                <Input />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="pharmacology" label="药理毒理">
                <TextArea rows={2} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="references" label="参考文献">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="monarch_ministers_assistants_couriers" label="君臣佐使">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="source" label="数据来源">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量导入Modal */}
      <Modal
        title="批量导入中成药数据"
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

export default Medics
