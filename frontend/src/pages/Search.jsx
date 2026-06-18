import React, { useState } from 'react'
import { Card, Input, Tabs, Button, Space, List, Tag, message, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { searchAPI } from '../services/api'

const Search = () => {
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const [prescriptionResults, setPrescriptionResults] = useState([])
  const [herbResults, setHerbResults] = useState([])
  const [semanticResults, setSemanticResults] = useState([])

  const handleSearch = async (type) => {
    const trimmedKeyword = keyword.trim()
    if (!trimmedKeyword) {
      message.warning('请输入搜索关键词')
      return
    }

    setLoading(true)

    try {
      if (type === 'prescriptions') {
        const result = await searchAPI.searchPrescriptions(trimmedKeyword)
        setPrescriptionResults(result || [])
      } else if (type === 'herbs') {
        const result = await searchAPI.searchHerbs(trimmedKeyword)
        setHerbResults(result || [])
      } else if (type === 'semantic') {
        const result = await searchAPI.semanticSearch({ query: trimmedKeyword })
        setSemanticResults(result || [])
      }
    } catch (error) {
      message.error('搜索失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const tabItems = [
    {
      key: 'prescriptions',
      label: '方剂搜索',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="输入方剂名称、功效等关键词"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={() => handleSearch('prescriptions')}
              style={{ width: 300 }}
            />
            <Button type="primary" icon={<SearchOutlined />} onClick={() => handleSearch('prescriptions')}>
              搜索
            </Button>
          </Space>
          <Spin spinning={loading}>
            <List
              dataSource={prescriptionResults}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={<span style={{ fontWeight: 'bold' }}>{item.name}</span>}
                    description={
                      <div>
                        <p>功效：{item.function_indication}</p>
                        {item.composition && <p>组成：{item.composition}</p>}
                        {item.usage_dosage && <p>用法用量：{item.usage_dosage}</p>}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Spin>
        </div>
      ),
    },
    {
      key: 'herbs',
      label: '药材搜索',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="输入药材名称、功效等关键词"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={() => handleSearch('herbs')}
              style={{ width: 300 }}
            />
            <Button type="primary" icon={<SearchOutlined />} onClick={() => handleSearch('herbs')}>
              搜索
            </Button>
          </Space>
          <Spin spinning={loading}>
            <List
              dataSource={herbResults}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={<span style={{ fontWeight: 'bold' }}>{item.name}</span>}
                    description={
                      <div>
                        <p>拼音：{item.pinyin}</p>
                        <p>性味：{item.nature}</p>
                        {item.function && <p>功能主治：{item.function}</p>}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Spin>
        </div>
      ),
    },
    {
      key: 'semantic',
      label: '语义搜索',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input
              placeholder="输入自然语言描述，例如：治疗感冒的方剂"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onPressEnter={() => handleSearch('semantic')}
              style={{ width: 300 }}
            />
            <Button type="primary" icon={<SearchOutlined />} onClick={() => handleSearch('semantic')}>
              语义搜索
            </Button>
          </Space>
          <Spin spinning={loading}>
            <List
              dataSource={semanticResults}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <span style={{ fontWeight: 'bold' }}>{item.name || item.name}</span>
                        <Tag color="blue">相似度: {(item.score || item.similarity * 100).toFixed(2)}%</Tag>
                      </Space>
                    }
                    description={item.description || item.function_indication}
                  />
                </List.Item>
              )}
            />
          </Spin>
        </div>
      ),
    },
  ]

  return (
    <div>
      <h2>智能搜索</h2>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  )
}

export default Search
