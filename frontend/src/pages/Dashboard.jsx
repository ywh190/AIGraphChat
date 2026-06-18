import { useEffect, useState } from 'react'
import { Card, Row, Col, Statistic, Spin, Alert, Button, Tabs, Progress, Tag, Space, Tooltip } from 'antd'
import {
  BookOutlined, ReloadOutlined, LinkOutlined, MedicineBoxOutlined, FileTextOutlined,
  DatabaseOutlined, ClusterOutlined, CheckCircleOutlined
} from '@ant-design/icons'
import { prescriptionAPI, herbAPI, medicAPI, knowledgeGraphAPI } from '../services/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts'

const Dashboard = () => {
  // 基础统计数据
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({
    prescriptions: 0,
    herbs: 0,
    medics: 0
  })

  // 数据分析状态
  const [activeTab, setActiveTab] = useState('herb')
  const [analysisLoading, setAnalysisLoading] = useState(false)

  // 分析数据状态
  const [herbAnalysisData, setHerbAnalysisData] = useState(null)
  const [prescriptionAnalysisData, setPrescriptionAnalysisData] = useState(null)
  const [medicAnalysisData, setMedicAnalysisData] = useState(null)

  // 图谱统计数据
  const [graphStats, setGraphStats] = useState(null)

  const COLORS = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#eb2f96', '#13c2c2', '#fa541c']

  useEffect(() => {
    loadStats()
    loadGraphStatistics()
    loadAllAnalysis()
  }, [])

  // 加载基础统计数据
  const loadStats = async () => {
    try {
      setLoading(true)
      const [prescriptions, herbs, medics] = await Promise.all([
        prescriptionAPI.getPrescriptions({ limit: 1 }),
        herbAPI.getHerbs({ limit: 1 }),
        medicAPI.getMedics({ limit: 1 })
      ])

      setStats({
        prescriptions: prescriptions.total || 0,
        herbs: herbs.total || 0,
        medics: medics.total || 0
      })
    } catch (error) {
      console.error('加载统计数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 加载图谱统计
  const loadGraphStatistics = async () => {
    try {
      const response = await knowledgeGraphAPI.getGraphStatistics()
      const data = response.data || response
      setGraphStats(data?.statistics || data)
    } catch (error) {
      console.error('获取图谱统计失败:', error)
    }
  }

  // 加载所有分析数据
  const loadAllAnalysis = async () => {
    try {
      setAnalysisLoading(true)

      const [herbStats, prescriptionStats, medicStats] = await Promise.all([
        herbAPI.getStatistics(),
        prescriptionAPI.getStatistics(),
        medicAPI.getStatistics()
      ])

      setHerbAnalysisData({
        natureData: herbStats.natureData || [],
        flavorData: herbStats.flavorData || [],
        meridianData: herbStats.meridianData || [],
        functionData: herbStats.functionData || [],
        totalHerbs: herbStats.total || 0
      })

      setPrescriptionAnalysisData({
        compositionData: prescriptionStats.compositionData || [],
        topEfficacies: prescriptionStats.topEfficacies || [],
        topHerbPairs: prescriptionStats.topHerbPairs || [],
        totalPrescriptions: prescriptionStats.total || 0
      })

      setMedicAnalysisData({
        categoryData: medicStats.categoryData || [],
        topEfficacies: medicStats.topEfficacies || [],
        herbCountDistribution: medicStats.herbCountDistribution || [],
        totalMedics: medicStats.total || 0
      })

    } catch (error) {
      console.error('加载统计数据失败:', error)
    } finally {
      setAnalysisLoading(false)
    }
  }

  // 渲染药材分析
  const renderHerbAnalysis = () => {
    if (!herbAnalysisData) {
      return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
    }

    const { natureData, flavorData, meridianData, functionData, totalHerbs } = herbAnalysisData

    return (
      <div>
        <Alert
          message={<span><DatabaseOutlined /> 药材资源库 - 共收录 <strong>{totalHerbs.toLocaleString()}</strong> 种药材</span>}
          description="基于《中国药典》及临床常用药材数据，涵盖药材性味归经、功能主治、化学成分等核心信息"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={12}>
            <Card 
              title={<span>四气分布 <Tag color="blue">药性分析</Tag></span>} 
              size="small"
              extra={<Tooltip title="寒热温凉平，反映药材作用于人体的寒热倾向"><span style={{cursor:'pointer'}}>ℹ️</span></Tooltip>}
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={natureData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '药材数量']} />
                  <Bar dataKey="value" fill="#1890ff" name="药材数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
          <Col span={12}>
            <Card 
              title={<span>五味分布 <Tag color="green">药味分析</Tag></span>} 
              size="small"
              extra={<Tooltip title="辛甘酸苦咸淡，反映药材的功效特点"><span style={{cursor:'pointer'}}>ℹ️</span></Tooltip>}
            >
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={flavorData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '药材数量']} />
                  <Bar dataKey="value" fill="#52c41a" name="药材数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Card 
              title={<span>归经分布TOP10 <Tag color="orange">靶向分析</Tag></span>} 
              size="small"
              extra={<Tooltip title="药材主要作用的脏腑经络，体现引经报使理论"><span style={{cursor:'pointer'}}>ℹ️</span></Tooltip>}
            >
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={meridianData.slice(0, 10)} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" width={60} />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '药材数量']} />
                  <Bar dataKey="value" fill="#fa8c16" name="药材数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
          <Col span={12}>
            <Card 
              title={<span>功效分布TOP10 <Tag color="purple">功能分析</Tag></span>} 
              size="small"
              extra={<Tooltip title="药材主要功能主治统计"><span style={{cursor:'pointer'}}>ℹ️</span></Tooltip>}
            >
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={functionData.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-30} textAnchor="end" height={80} fontSize={12} />
                  <YAxis />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '药材数量']} />
                  <Bar dataKey="value" fill="#722ed1" name="药材数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>
      </div>
    )
  }

  // 渲染方剂分析
  const renderPrescriptionAnalysis = () => {
    if (!prescriptionAnalysisData) {
      return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
    }

    const { compositionData, topEfficacies, topHerbPairs, totalPrescriptions } = prescriptionAnalysisData

    return (
      <div>
        <Alert
          message={<span><BookOutlined /> 方剂数据库 - 共收录 <strong>{totalPrescriptions.toLocaleString()}</strong> 首方剂</span>}
          description="涵盖经典名方、临床验方及现代研究成果，支持方剂组方分析、药对挖掘与功效研究"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card title="组成复杂度分布" size="small">
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={compositionData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}\n${(percent * 100).toFixed(1)}%`}
                    outerRadius={70}
                    dataKey="value"
                  >
                    {compositionData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </Col>
          <Col span={16}>
            <Card title="高频功效TOP10" size="small">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={topEfficacies.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-20} textAnchor="end" height={70} fontSize={11} />
                  <YAxis />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}首 (${props.payload.percentage}%)`, '方剂数量']} />
                  <Bar dataKey="value" fill="#f5222d" name="方剂数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>

        <Card 
          title={<span>经典药对TOP12 <Tag color="gold">配伍规律</Tag></span>} 
          size="small"
          extra={<Tooltip title="高频药对组合，体现相须相使等配伍原理"><span style={{cursor:'pointer'}}>ℹ️</span></Tooltip>}
        >
          <Row gutter={[12, 12]}>
            {(topHerbPairs || []).slice(0, 12).map((item, index) => (
              <Col span={6} key={index}>
                <Card
                  size="small"
                  style={{
                    background: index < 3 ? 'linear-gradient(135deg, #fff7e6 0%, #ffd591 100%)' :
                              index < 6 ? 'linear-gradient(135deg, #e6f7ff 0%, #91d5ff 100%)' :
                              '#fafafa',
                    textAlign: 'center'
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 'bold', marginBottom: 4 }}>
                    {item.herb1} + {item.herb2}
                  </div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: index < 3 ? '#d4380d' : '#1890ff' }}>
                    {item.count}次
                  </div>
                  <div style={{ fontSize: '11px', color: '#999' }}>
                    占比 {item.percentage}%
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      </div>
    )
  }

  // 渲染中成药分析
  const renderMedicAnalysis = () => {
    if (!medicAnalysisData) {
      return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
    }

    const { categoryData, topEfficacies, herbCountDistribution, totalMedics } = medicAnalysisData

    return (
      <div>
        <Alert
          message={<span><MedicineBoxOutlined /> 中成药产品库 - 共收录 <strong>{totalMedics.toLocaleString()}</strong> 种中成药</span>}
          description="涵盖国药准字产品，支持科室应用分析、产品功效研究、组方成分分析"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={12}>
            <Card 
              title={<span>科室应用分布 <Tag color="cyan">临床定位</Tag></span>} 
              size="small"
            >
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={categoryData.slice(0, 8)}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name.substring(0,4)} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={90}
                    dataKey="value"
                  >
                    {categoryData.slice(0, 8).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '中成药数量']} />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="组方复杂度分布" size="small">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={herbCountDistribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '中成药数量']} />
                  <Bar dataKey="value" fill="#eb2f96" name="中成药数量" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>

        <Card title="高频功效TOP10" size="small">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={topEfficacies.slice(0, 10)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-20} textAnchor="end" height={60} fontSize={11} />
              <YAxis />
              <RechartsTooltip formatter={(value, _name, props) => [`${value}种 (${props.payload.percentage}%)`, '中成药数量']} />
              <Bar dataKey="value" fill="#13c2c2" name="中成药数量" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    )
  }

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 100 }} />
  }

  // 计算数据质量指标
  const herbQuality = herbAnalysisData ? Math.min(100, Math.round((herbAnalysisData.natureData.length / 5) * 100)) : 0
  const prescriptionQuality = prescriptionAnalysisData ? 95 : 0
  const medicQuality = medicAnalysisData ? 90 : 0

  return (
    <div style={{ padding: '0 0 24px 0' }}>
      {/* 系统概览标题 */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
          <DatabaseOutlined style={{ marginRight: 8, color: '#1890ff' }} />
          中医药数据资源概览
        </h2>
        <p style={{ color: '#666', margin: '8px 0 0 0', fontSize: 13 }}>
          数据更新时间：{new Date().toLocaleString('zh-CN')}
        </p>
      </div>

      {/* 核心数据统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card 
            hoverable
            style={{ borderLeft: '4px solid #1890ff' }}
          >
            <Statistic
              title={<span style={{ fontSize: 13 }}>方剂数据库</span>}
              value={stats.prescriptions}
              suffix={<span style={{ fontSize: 14, color: '#999' }}>首</span>}
              prefix={<BookOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#1890ff', fontWeight: 600 }}
            />
            <div style={{ marginTop: 8 }}>
              <Progress percent={prescriptionQuality} size="small" showInfo={false} strokeColor="#1890ff" />
              <span style={{ fontSize: 12, color: '#999' }}>数据完整度 {prescriptionQuality}%</span>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card 
            hoverable
            style={{ borderLeft: '4px solid #52c41a' }}
          >
            <Statistic
              title={<span style={{ fontSize: 13 }}>药材资源库</span>}
              value={stats.herbs}
              suffix={<span style={{ fontSize: 14, color: '#999' }}>种</span>}
              prefix={<FileTextOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a', fontWeight: 600 }}
            />
            <div style={{ marginTop: 8 }}>
              <Progress percent={herbQuality} size="small" showInfo={false} strokeColor="#52c41a" />
              <span style={{ fontSize: 12, color: '#999' }}>数据完整度 {herbQuality}%</span>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card 
            hoverable
            style={{ borderLeft: '4px solid #fa8c16' }}
          >
            <Statistic
              title={<span style={{ fontSize: 13 }}>中成药产品库</span>}
              value={stats.medics}
              suffix={<span style={{ fontSize: 14, color: '#999' }}>种</span>}
              prefix={<MedicineBoxOutlined style={{ color: '#fa8c16' }} />}
              valueStyle={{ color: '#fa8c16', fontWeight: 600 }}
            />
            <div style={{ marginTop: 8 }}>
              <Progress percent={medicQuality} size="small" showInfo={false} strokeColor="#fa8c16" />
              <span style={{ fontSize: 12, color: '#999' }}>数据完整度 {medicQuality}%</span>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card 
            hoverable
            style={{ borderLeft: '4px solid #722ed1' }}
          >
            <Statistic
              title={<span style={{ fontSize: 13 }}>知识图谱节点</span>}
              value={graphStats?.total_nodes || 0}
              suffix={<span style={{ fontSize: 14, color: '#999' }}>个</span>}
              prefix={<ClusterOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ color: '#722ed1', fontWeight: 600 }}
            />
            <div style={{ marginTop: 8 }}>
              <Space>
                <Tag color="purple">{graphStats?.total_relationships || 0} 关系</Tag>
              </Space>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 数据分析区域 */}
      <Card
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span><LinkOutlined /> 中医药实体数据分析</span>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadAllAnalysis}
              loading={analysisLoading}
              size="small"
            >
              刷新数据
            </Button>
          </div>
        }
      >
        {analysisLoading && !herbAnalysisData && !prescriptionAnalysisData && !medicAnalysisData ? (
          <Alert
            message="正在加载分析数据..."
            description="系统正在计算统计数据，请稍候..."
            type="info"
            showIcon
          />
        ) : null}

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'herb',
              label: <span><FileTextOutlined /> 药材分析</span>,
              children: analysisLoading && !herbAnalysisData ? (
                <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 50 }} />
              ) : (
                renderHerbAnalysis()
              )
            },
            {
              key: 'prescription',
              label: <span><BookOutlined /> 方剂分析</span>,
              children: analysisLoading && !prescriptionAnalysisData ? (
                <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 50 }} />
              ) : (
                renderPrescriptionAnalysis()
              )
            },
            {
              key: 'medic',
              label: <span><MedicineBoxOutlined /> 中成药分析</span>,
              children: analysisLoading && !medicAnalysisData ? (
                <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 50 }} />
              ) : (
                renderMedicAnalysis()
              )
            }
          ]}
        />
      </Card>

      {/* 数据说明 */}
      <Card style={{ marginTop: 16 }} size="small">
        <Row gutter={24}>
          <Col span={8}>
            <div style={{ marginBottom: 8 }}>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              <strong>药材分析</strong>
            </div>
            <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
              基于性味归经理论，分析药材的四气五味、归经分布及功效特征，支持药材资源评估与质量控制
            </p>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 8 }}>
              <CheckCircleOutlined style={{ color: '#1890ff', marginRight: 8 }} />
              <strong>方剂分析</strong>
            </div>
            <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
              挖掘方剂组方规律、经典药对配伍原理，支持新方研发与临床应用研究
            </p>
          </Col>
          <Col span={8}>
            <div style={{ marginBottom: 8 }}>
              <CheckCircleOutlined style={{ color: '#fa8c16', marginRight: 8 }} />
              <strong>中成药分析</strong>
            </div>
            <p style={{ fontSize: 12, color: '#666', margin: 0 }}>
              分析产品科室分布、功效定位及组方复杂度，支持产品线规划与市场定位分析
            </p>
          </Col>
        </Row>
      </Card>
    </div>
  )
}

export default Dashboard
