import React, { useEffect, useState } from 'react'
import { Table, Button, Space, Input, Modal, Form, message, Tooltip, Upload, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { prescriptionAPI } from '../services/api'

const { Option } = Select

// 截断文本函数
const truncateText = (text, maxLength = 50) => {
  if (!text) return '-'
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

const Prescriptions = () => {
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
    { title: '方剂名称', dataIndex: 'name', key: 'name', width: 150, fixed: 'left' },
    { 
      title: '组成', 
      dataIndex: 'composition', 
      key: 'composition', 
      width: 250,
      render: (text) => (
        <Tooltip title={text}>
          <span>{truncateText(text, 40)}</span>
        </Tooltip>
      )
    },
    { 
      title: '功能主治', 
      dataIndex: 'function_indication', 
      key: 'function_indication', 
      width: 250,
      render: (text) => (
        <Tooltip title={text}>
          <span>{truncateText(text, 40)}</span>
        </Tooltip>
      )
    },
    { 
      title: '用法用量', 
      dataIndex: 'usage_dosage', 
      key: 'usage_dosage', 
      width: 200,
      render: (text) => truncateText(text, 35)
    },
    { 
      title: '数据来源', 
      dataIndex: 'source', 
      key: 'source', 
      width: 150,
      render: (text) => truncateText(text, 25)
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
        const result = await prescriptionAPI.searchPrescriptions(keyword, type, skip, pageSize)
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
        const result = await prescriptionAPI.getPrescriptions({ skip, limit: pageSize })
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
          await prescriptionAPI.deletePrescription(id)
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
        await prescriptionAPI.updatePrescription(editingRecord.id, values)
        message.success('更新成功')
      } else {
        await prescriptionAPI.createPrescription(values)
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
        name: '麻黄汤',
        composition: '麻黄（去节）三两，桂枝（去皮）二两，甘草（炙）一两，杏仁（去皮尖）七十个',
        function_indication: '发汗解表，宣肺平喘。主治外感风寒表实证，症见恶寒发热、头痛身痛、无汗而喘、苔薄白、脉浮紧',
        usage_dosage: '水煎服，分三次服',
        source: '伤寒论'
      }
    ]

    const headers = [
      'name', 'composition', 'function_indication', 'usage_dosage', 'source'
    ]

    const headerNames = [
      '方剂名称', '药物组成', '功能主治', '用法用量', '数据来源'
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
    a.download = 'prescription_sample_data.csv'
    a.click()
    URL.revokeObjectURL(url)

    message.success('示例数据已导出')
  }

  // 导出所有数据
  const handleExportAll = async (format = 'csv') => {
    try {
      const response = await prescriptionAPI.exportAll(format)
      // 创建Blob对象
      const blob = new Blob([response], { type: format === 'csv' ? 'text/csv' : 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `prescriptions_export.${format}`
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
          const expectedHeaders = ['方剂名称', '药物组成', '功能主治', '用法用量', '数据来源']

          // 中文表头到英文字段名的映射
          const headerMap = {
            '方剂名称': 'name',
            '药物组成': 'composition',
            '功能主治': 'function_indication',
            '用法用量': 'usage_dosage',
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
          const result = await prescriptionAPI.bulkImport(records)

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
          placeholder="搜索方剂..."
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
              新增方剂
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
        title="方剂详情"
        open={viewModalVisible}
        onCancel={() => setViewModalVisible(false)}
        footer={null}
        width={800}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
      >
        {viewingRecord && (
          <div style={{ lineHeight: 2 }}>
            <p><strong>ID:</strong> {viewingRecord.id}</p>
            <p><strong>方剂名称:</strong> {viewingRecord.name}</p>
            <p><strong>药物组成:</strong> {viewingRecord.composition || '-'}</p>
            <p><strong>功能主治:</strong> {viewingRecord.function_indication || '-'}</p>
            <p><strong>用法用量:</strong> {viewingRecord.usage_dosage || '-'}</p>
            <p><strong>数据来源:</strong> {viewingRecord.source || '-'}</p>
          </div>
        )}
      </Modal>

      <Table
        loading={loading}
        columns={columns}
        dataSource={data}
        rowKey="id"
        scroll={{ x: 1200 }}
        pagination={pagination}
        onChange={handleTableChange}
      />
      <Modal
        title={editingRecord ? '编辑方剂' : '新增方剂'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={800}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="中文名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="composition" label="药物组成">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="function_indication" label="功能主治">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="usage_dosage" label="用法用量">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="source" label="数据来源">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量导入Modal */}
      <Modal
        title="批量导入方剂数据"
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

export default Prescriptions
