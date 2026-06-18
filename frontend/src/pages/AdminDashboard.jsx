import React, { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Button, Space, Tag, Divider, Progress, message, Modal, Descriptions, Spin, Alert, Form, Input, Select } from 'antd'
import { DatabaseOutlined, UserOutlined, MedicineBoxOutlined, ExperimentOutlined, SyncOutlined, CheckCircleOutlined, WarningOutlined, ReloadOutlined, LockOutlined, PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import api, { syncAPI, userAPI, isAdmin } from '../services/api'
import { useNavigate } from 'react-router-dom'

const AdminDashboard = () => {
  const navigate = useNavigate()

  // 使用 ref 存储轮询 interval ID，防止多个轮询同时运行
  const pollIntervalRef = React.useRef(null)
  const hasCheckedProgressRef = React.useRef(false)

  // 检查管理员权限
  useEffect(() => {
    if (!isAdmin()) {
      message.error('您需要管理员权限才能访问此页面')
      navigate('/login')
    }
  }, [navigate])
  const [statistics, setStatistics] = useState({
    prescriptions: 0,
    herbs: 0,
    medics: 0
  })
  const [loading, setLoading] = useState(false)

  // 数据同步相关状态
  const [syncStats, setSyncStats] = useState({
    mysql: { prescriptions: 0, herbs: 0, medics: 0 },
    neo4j: { prescriptions: 0, herbs: 0, medics: 0, relationships: 0 },
    sync_status: { last_sync_time: null, in_progress: false }
  })
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncProgress, setSyncProgress] = useState({
    progress: 0,
    current_step: '',
    message: '',
    status: 'idle',
    in_progress: false
  })
  const [progressModalVisible, setProgressModalVisible] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [validationModalVisible, setValidationModalVisible] = useState(false)

  // 用户管理相关状态
  const [users, setUsers] = useState([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [userModalVisible, setUserModalVisible] = useState(false)
  const [userFormMode, setUserFormMode] = useState('create') // 'create' | 'edit'
  const [currentUser, setCurrentUser] = useState(null)
  const [userForm] = Form.useForm()

  // 获取系统统计信息
  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        setLoading(true)
        // axios拦截器已返回response.data，但后端返回格式是 {success: true, data: {...}}
        const response = await api.get('/admin/statistics/overview')
        // 从 response.data 中提取实际统计数据
        const data = response?.data || response
        setStatistics(data)
      } catch (error) {
        console.error('获取统计信息失败:', error)
        if (error.response?.status === 401) {
          message.warning('需要管理员权限，请以管理员身份登录')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchStatistics()
  }, [])

  // 获取同步统计信息
  const fetchSyncStatistics = async () => {
    try {
      // axios拦截器已返回response.data，但后端返回格式是 {success: true, data: {...}}
      const response = await syncAPI.getSyncStatistics()
      // 从 response.data 中提取实际统计数据
      const data = response?.data || response
      if (data) {
        setSyncStats(data)
      }
    } catch (error) {
      console.error('获取同步统计失败:', error)
      message.error('获取同步统计失败')
    }
  }

  useEffect(() => {
    fetchSyncStatistics()

    // 检查是否有正在进行的同步任务（只检查一次）
    const checkSyncProgress = async () => {
      // 如果已经有轮询在运行，不再启动新的
      if (pollIntervalRef.current) {
        console.log('[SYNC] 已有轮询在运行，跳过检查')
        return
      }
      
      try {
        const response = await syncAPI.getSyncProgress()
        const progressData = response?.data || response
        
        console.log('[SYNC] 完整进度数据:', JSON.stringify(progressData, null, 2))
        
        // 只有当状态为 running 时才开启轮询和弹窗
        const status = progressData?.status || 'idle'
        const inProgress = progressData?.in_progress
        
        console.log('[SYNC] 解析结果:', { 
          status, 
          inProgress, 
          typeOfInProgress: typeof inProgress,
          shouldShowModal: status === 'running' && inProgress === true
        })
        
        // 只有真正在运行中才显示弹窗和开启轮询
        if (status === 'running' && inProgress === true) {
          console.log('[SYNC] 检测到同步任务运行中，开启轮询')
          setSyncProgress(progressData)
          setProgressModalVisible(true)
          // 开始轮询进度
          pollIntervalRef.current = setInterval(async () => {
            const shouldContinue = await pollSyncProgress()
            if (!shouldContinue && pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
              pollIntervalRef.current = null
            }
          }, 1000)
        } else {
          // 如果没有同步任务在运行，不显示弹窗，不设置进度数据
          console.log('[SYNC] 没有同步任务运行，不显示弹窗')
        }
      } catch (error) {
        console.error('检查同步进度失败:', error)
      }
    }

    // 只在第一次加载时检查
    if (!hasCheckedProgressRef.current) {
      hasCheckedProgressRef.current = true
      checkSyncProgress()
    }

    // 组件卸载时清除轮询
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }
  }, [])

  // 触发全量同步
  const handleFullSync = async () => {
    Modal.confirm({
      title: '确认执行全量同步？',
      content: '这将删除Neo4j的所有数据，重新把MySQL中的所有数据同步到Neo4j（可能花费大量时间！）。',
      onOk: async () => {
        setSyncLoading(true)
        try {
          // 使用后台同步,显示进度
          const response = await syncAPI.backgroundSync({
            sync_prescriptions: true,
            sync_herbs: true,
            sync_medics: true,
            sync_relationships: true,
            sync_attributes: true
          })
          
          if (response && (response.success || response.status === 'running')) {
            message.success('同步任务已启动')
            // 显示进度窗口
            setProgressModalVisible(true)
            // 先清除可能存在的旧轮询
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
            }
            // 开始轮询进度
            pollIntervalRef.current = setInterval(async () => {
              const shouldContinue = await pollSyncProgress()
              if (!shouldContinue && pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current)
                pollIntervalRef.current = null
              }
            }, 1000)
          } else {
            message.error('同步启动失败: ' + (response?.message || '未知错误'))
          }
        } catch (error) {
          console.error('同步失败:', error)
          message.error('同步失败: ' + (error.response?.data?.detail || error.message))
        } finally {
          setSyncLoading(false)
        }
      }
    })
  }

  // 触发增量同步（使用后台同步，显示进度）
  const handleIncrementalSync = async () => {
    Modal.confirm({
      title: '确认执行增量同步？',
      content: '这将只同步自上次同步以来新增或修改的数据（不会删除现有数据）。',
      onOk: async () => {
        setSyncLoading(true)
        try {
          // 使用后台同步，支持进度显示
          const response = await syncAPI.backgroundIncrementalSync({
            sync_prescriptions: true,
            sync_herbs: true,
            sync_medics: true
          })

          if (response && (response.success || response.status === 'running')) {
            message.success('增量同步任务已启动')
            // 显示进度窗口
            setProgressModalVisible(true)
            // 先清除可能存在的旧轮询
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
            }
            // 开始轮询进度
            pollIntervalRef.current = setInterval(async () => {
              const shouldContinue = await pollSyncProgress()
              if (!shouldContinue && pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current)
                pollIntervalRef.current = null
              }
            }, 1000)
          } else {
            message.error('增量同步启动失败: ' + (response?.message || '未知错误'))
          }
        } catch (error) {
          console.error('增量同步失败:', error)
          message.error('增量同步失败: ' + (error.response?.data?.detail || error.message))
        } finally {
          setSyncLoading(false)
        }
      }
    })
  }

  // 验证数据一致性
  const handleValidateConsistency = async () => {
    setSyncLoading(true)
    try {
      // axios拦截器已返回response.data，但后端返回格式是 {success: true, data: {...}}
      const response = await syncAPI.validateConsistency()
      // 从 response.data 中提取实际验证结果
      const data = response?.data || response
      setValidationResult(data)
      setValidationModalVisible(true)
      const msg = response?.message || '验证完成'
      message.success(msg)
    } catch (error) {
      console.error('验证失败:', error)
      message.error('验证失败: ' + (error.response?.data?.detail || error.message))
    } finally {
      setSyncLoading(false)
    }
  }

  // 清除同步缓存
  const handleClearCache = async () => {
    Modal.confirm({
      title: '确认清除同步缓存？',
      content: '这将清除所有同步相关的缓存数据。',
      onOk: async () => {
        try {
          await syncAPI.clearSyncCache()
          message.success('同步缓存已清除')
          // 清除轮询
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
          // 关闭进度窗口
          setProgressModalVisible(false)
          // 重置进度状态
          setSyncProgress({
            progress: 0,
            current_step: 'idle',
            message: '',
            status: 'idle',
            in_progress: false
          })
        } catch (error) {
          console.error('清除缓存失败:', error)
          message.error('清除缓存失败')
        }
      }
    })
  }

  // 格式化步骤名称
  const formatStepName = (step) => {
    const stepNames = {
      'idle': '空闲',
      'sync_prescriptions': '同步方剂',
      'sync_herbs': '同步药材',
      'sync_medics': '同步中成药',
      'sync_prescription_relationships': '同步方剂-药材关系',
      'sync_medic_relationships': '同步中成药-药材关系',
      'sync_attributes': '同步属性数据',
      'sync_efficacies': '同步功效',
      'sync_natures': '同步性味',
      'sync_meridians': '同步归经',
      'sync_herb_efficacies': '建立药材-功效关系',
      'sync_herb_natures': '建立药材-性味关系',
      'sync_herb_meridians': '建立药材-归经关系',
      'clear_neo4j': '清空Neo4j数据',
      'completed': '已完成',
      'failed': '失败',
      'error': '错误'
    }
    return stepNames[step] || step
  }

  // 获取进度状态
  const getProgressStatus = () => {
    if (syncProgress.status === 'completed' || syncProgress.progress >= 100) {
      return 'success'
    }
    if (syncProgress.status === 'failed' || syncProgress.status === 'error') {
      return 'exception'
    }
    if (syncProgress.in_progress) {
      return 'active'
    }
    return 'normal'
  }

  // 获取进度状态颜色
  const getProgressStatusColor = () => {
    if (syncProgress.status === 'completed' || syncProgress.progress >= 100) {
      return 'success'
    }
    if (syncProgress.status === 'failed' || syncProgress.status === 'error') {
      return 'error'
    }
    if (syncProgress.in_progress) {
      return 'processing'
    }
    return 'default'
  }

  // 获取进度状态文本
  const getProgressStatusText = () => {
    if (syncProgress.status === 'completed' || syncProgress.progress >= 100) {
      return '已完成'
    }
    if (syncProgress.status === 'failed') {
      return '失败'
    }
    if (syncProgress.status === 'error') {
      return '错误'
    }
    if (syncProgress.in_progress) {
      return '进行中'
    }
    return '空闲'
  }

  // 查看进度
  const handleViewProgress = async () => {
    try {
      const response = await syncAPI.getSyncProgress()
      const progressData = response?.data || response
      setSyncProgress(progressData)
      setProgressModalVisible(true)

      // 如果正在同步且没有正在运行的轮询，开始轮询
      if (progressData?.in_progress && !pollIntervalRef.current) {
        pollIntervalRef.current = setInterval(async () => {
          const shouldContinue = await pollSyncProgress()
          if (!shouldContinue && pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
        }, 1000)
      }
    } catch (error) {
      console.error('获取进度失败:', error)
      message.error('获取进度失败')
    }
  }

  // 轮询同步进度
  const pollSyncProgress = async () => {
    try {
      const response = await syncAPI.getSyncProgress()
      const progressData = response?.data || response
      setSyncProgress(progressData)
      
      // 获取状态，确保有默认值
      const status = progressData?.status || 'idle'
      
      // 只有在状态为 running 时才继续轮询，其他状态都停止
      if (status !== 'running') {
        // 同步成功完成
        if (status === 'completed' || progressData?.progress >= 100) {
          message.success('同步完成！')
        } else if (status === 'failed' || status === 'error') {
          message.error('同步失败')
        }
        setProgressModalVisible(false)
        setSyncProgress({
          progress: 0,
          current_step: 'idle',
          message: '',
          status: 'idle',
          in_progress: false
        })
        // 刷新统计数据
        setTimeout(fetchSyncStatistics, 1000)
        return false
      }
      
      return true // 继续轮询
    } catch (error) {
      console.error('获取同步进度失败:', error)
      return false
    }
  }

  // ========== 用户管理函数 ==========

  // 获取用户列表
  const fetchUsers = async () => {
    try {
      setUsersLoading(true)
      const response = await userAPI.getUsers(0, 1000) // 获取所有用户
      setUsers(response)
    } catch (error) {
      console.error('获取用户列表失败:', error)
      message.error('获取用户列表失败: ' + (error.response?.data?.detail || error.message))
    } finally {
      setUsersLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  // 打开创建用户模态框
  const handleCreateUser = () => {
    setUserFormMode('create')
    setCurrentUser(null)
    userForm.resetFields()
    setUserModalVisible(true)
  }

  // 打开编辑用户模态框
  const handleEditUser = (user) => {
    setUserFormMode('edit')
    setCurrentUser(user)
    userForm.setFieldsValue({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active
    })
    setUserModalVisible(true)
  }

  // 删除用户
  const handleDeleteUser = (user) => {
    Modal.confirm({
      title: '确认删除用户？',
      content: `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
      okText: '确认',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await userAPI.deleteUser(user.id)
          message.success('用户已删除')
          fetchUsers() // 刷新用户列表
        } catch (error) {
          console.error('删除用户失败:', error)
          message.error('删除用户失败: ' + (error.response?.data?.detail || error.message))
        }
      }
    })
  }

  // 提交用户表单
  const handleUserSubmit = async (values) => {
    try {
      if (userFormMode === 'create') {
        // 创建用户
        const createData = {
          username: values.username,
          email: values.email,
          full_name: values.full_name,
          password: values.password,
          role: values.role || 'user',
          is_active: values.is_active !== undefined ? values.is_active : true
        }
        await userAPI.createUser(createData)
        message.success('用户创建成功')
      } else {
        // 更新用户 - 只发送有值的字段
        const updateData = {}
        if (values.email) updateData.email = values.email
        if (values.full_name) updateData.full_name = values.full_name
        if (values.password) updateData.password = values.password
        if (values.role) updateData.role = values.role
        if (values.is_active !== undefined) updateData.is_active = values.is_active
        await userAPI.updateUser(currentUser.id, updateData)
        message.success('用户更新成功')
      }
      setUserModalVisible(false)
      fetchUsers() // 刷新用户列表
    } catch (error) {
      console.error('提交用户失败:', error)
      message.error('操作失败: ' + (error.response?.data?.detail || error.message))
    }
  }

  // 切换用户激活状态
  const handleToggleUserActive = async (user) => {
    try {
      await userAPI.updateUser(user.id, { is_active: !user.is_active })
      message.success(user.is_active ? '用户已禁用' : '用户已启用')
      fetchUsers() // 刷新用户列表
    } catch (error) {
      console.error('更新用户状态失败:', error)
      message.error('更新用户状态失败')
    }
  }

  // 用户表格列配置
  const userColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '全名',
      dataIndex: 'full_name',
      key: 'full_name',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: role => (
        <Tag color={role === 'admin' || role === 'ADMIN' ? 'blue' : 'green'}>
          {role === 'admin' || role === 'ADMIN' ? '管理员' : '普通用户'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (isActive) => (
        <Tag color={isActive ? 'success' : 'default'}>
          {isActive ? '活跃' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditUser(record)}
          >
            编辑
          </Button>
          <Button
            size="small"
            type={record.is_active ? 'default' : 'primary'}
            onClick={() => handleToggleUserActive(record)}
          >
            {record.is_active ? '禁用' : '启用'}
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteUser(record)}
            disabled={record.username === 'admin'} // 不能删除默认管理员
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {!isAdmin() && (
        <Alert
          message="需要管理员权限"
          description="您需要以管理员身份登录才能访问此页面。"
          type="warning"
          showIcon
          icon={<LockOutlined />}
          style={{ marginBottom: 24 }}
          action={
            <Button type="primary" size="small" onClick={() => navigate('/login')}>
              去登录
            </Button>
          }
        />
      )}

      <h2>管理员控制台</h2>
      
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="方剂总数"
              value={statistics.prescriptions}
              prefix={<MedicineBoxOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="药材总数"
              value={statistics.herbs}
              prefix={<ExperimentOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="中成药总数"
              value={statistics.medics}
              prefix={<DatabaseOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="用户总数"
              value={users.length}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#eb2f96' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider />

      {/* 用户管理模块 */}
      <Card
        title={<><UserOutlined /> 用户管理</>}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreateUser}
            size="small"
          >
            添加用户
          </Button>
        }
        loading={usersLoading}
      >
        <Table
          columns={userColumns}
          dataSource={users}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          scroll={{ y: 400 }}
        />
      </Card>

      <Divider />

      {/* 数据同步管理模块 */}
      <Card 
        title={<><SyncOutlined /> 数据同步管理（MySQL ↔ Neo4j）</>}
        extra={
          <Button 
            icon={<ReloadOutlined />} 
            onClick={fetchSyncStatistics}
            loading={syncLoading}
            size="small"
          >
            刷新状态
          </Button>
        }
      >
        <Row gutter={[16, 16]}>
          {/* MySQL 统计 */}
          <Col span={12}>
            <Card title="MySQL 数据量" size="small" type="inner">
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic 
                    title="方剂" 
                    value={syncStats.mysql?.prescriptions || 0} 
                    suffix="条"
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="药材" 
                    value={syncStats.mysql?.herbs || 0} 
                    suffix="条"
                  />
                </Col>
                <Col span={8}>
                  <Statistic 
                    title="中成药" 
                    value={syncStats.mysql?.medics || 0} 
                    suffix="条"
                  />
                </Col>
              </Row>
            </Card>
          </Col>

          {/* Neo4j 统计 */}
          <Col span={12}>
            <Card title="Neo4j 数据量" size="small" type="inner">
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic 
                    title="方剂" 
                    value={syncStats.neo4j?.prescriptions || 0} 
                    suffix="条"
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="药材" 
                    value={syncStats.neo4j?.herbs || 0} 
                    suffix="条"
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="中成药" 
                    value={syncStats.neo4j?.medics || 0} 
                    suffix="条"
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="关系" 
                    value={syncStats.neo4j?.relationships || 0} 
                    suffix="条"
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>

        <Divider />

        {/* 数据一致性对比 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Card title="数据一致性对比" size="small" type="inner">
              <Row gutter={16}>
                {['prescriptions', 'herbs', 'medics'].map((type) => {
                  const mysqlCount = syncStats.mysql?.[type] || 0
                  const neo4jCount = syncStats.neo4j?.[type] || 0
                  const diff = mysqlCount - neo4jCount
                  const isConsistent = diff === 0
                  const percent = mysqlCount > 0 ? Math.round((neo4jCount / mysqlCount) * 100) : 100
                  
                  const typeNames = { prescriptions: '方剂', herbs: '药材', medics: '中成药' }
                  
                  return (
                    <Col span={8} key={type}>
                      <div style={{ marginBottom: 8 }}>
                        <span style={{ fontWeight: 'bold' }}>{typeNames[type]}:</span>
                        <Tag color={isConsistent ? 'success' : 'warning'} style={{ marginLeft: 8 }}>
                          {isConsistent ? <CheckCircleOutlined /> : <WarningOutlined />} 
                          {isConsistent ? '一致' : `差异 ${Math.abs(diff)}`}
                        </Tag>
                      </div>
                      <Progress 
                        percent={percent} 
                        status={isConsistent ? 'success' : 'exception'}
                        size="small"
                        format={(p) => `${p}%`}
                      />
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        MySQL: {mysqlCount} / Neo4j: {neo4jCount}
                      </div>
                    </Col>
                  )
                })}
              </Row>
            </Card>
          </Col>
        </Row>

        {/* 同步操作按钮 */}
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Space>
              <Button 
                type="primary" 
                icon={<SyncOutlined />}
                onClick={handleFullSync}
                loading={syncLoading}
              >
                全量同步
              </Button>
              <Button 
                icon={<SyncOutlined />}
                onClick={handleIncrementalSync}
                loading={syncLoading}
              >
                增量同步
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleViewProgress}
              >
                查看进度
              </Button>
              <Button 
                icon={<CheckCircleOutlined />}
                onClick={handleValidateConsistency}
                loading={syncLoading}
              >
                验证一致性
              </Button>
              <Button 
                danger
                onClick={handleClearCache}
                loading={syncLoading}
              >
                清除缓存
              </Button>
            </Space>
            <span style={{ marginLeft: 16, color: '#666' }}>
              上次同步: {syncStats.sync_status?.last_sync_time 
                ? new Date(syncStats.sync_status.last_sync_time).toLocaleString('zh-CN') 
                : '未同步'}
              {syncStats.sync_status?.in_progress && (
                <Tag color="processing" style={{ marginLeft: 8 }}>同步中...</Tag>
              )}
            </span>
          </Col>
        </Row>
      </Card>

      {/* 一致性验证结果弹窗 */}
      <Modal
        title="数据一致性验证结果"
        open={validationModalVisible}
        onCancel={() => setValidationModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setValidationModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {validationResult ? (
          <>
            <div style={{ marginBottom: 16 }}>
              <Tag color={validationResult.consistent ? 'success' : 'error'} size="large">
                {validationResult.consistent ? '数据一致' : '发现数据不一致'}
              </Tag>
            </div>

            {/* 完整数据对比 */}
            {validationResult.mysql_counts && validationResult.neo4j_counts && (
              <>
                <Descriptions title="数据统计对比" bordered column={3} size="small">
                  <Descriptions.Item label="方剂">
                    <div>MySQL: {validationResult.mysql_counts.prescriptions || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.prescriptions || 0} 条</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="药材">
                    <div>MySQL: {validationResult.mysql_counts.herbs || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.herbs || 0} 条</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="中成药">
                    <div>MySQL: {validationResult.mysql_counts.medics || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.medics || 0} 条</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="功效">
                    <div>MySQL: {validationResult.mysql_counts.efficacies || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.efficacies || 0} 条</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="性味">
                    <div>MySQL: {validationResult.mysql_counts.natures || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.natures || 0} 条</div>
                  </Descriptions.Item>
                  <Descriptions.Item label="归经">
                    <div>MySQL: {validationResult.mysql_counts.meridians || 0} 条</div>
                    <div>Neo4j: {validationResult.neo4j_counts.meridians || 0} 条</div>
                  </Descriptions.Item>
                </Descriptions>
              </>
            )}

            {validationResult.differences && validationResult.differences.length > 0 && (
              <Descriptions title="差异详情" bordered column={1} size="small" style={{ marginTop: 16 }}>
                {validationResult.differences.map((diff, index) => {
                  const entityNames = {
                    'prescriptions': '方剂',
                    'herbs': '药材',
                    'efficacies': '功效',
                    'medics': '中成药',
                    'natures': '性味',
                    'meridians': '归经'
                  }
                  return (
                    <Descriptions.Item key={index} label={entityNames[diff.entity] || diff.entity}>
                      MySQL: {diff.mysql_count} 条<br/>
                      Neo4j: {diff.neo4j_count} 条<br/>
                      差异: <span style={{ color: diff.difference > 0 ? 'red' : 'green' }}>
                        {diff.difference > 0 ? '+' : ''}{diff.difference}
                      </span>
                    </Descriptions.Item>
                  )
                })}
              </Descriptions>
            )}

            {validationResult.differences && validationResult.differences.length === 0 && (
              <p style={{ color: '#52c41a', marginTop: 16 }}>✓ MySQL 和 Neo4j 数据完全一致</p>
            )}
          </>
        ) : (
          <Spin tip="加载中..." />
        )}
      </Modal>

      {/* 同步进度弹窗 */}
      <Modal
        title="数据同步进度"
        open={progressModalVisible}
        onCancel={() => {
          setProgressModalVisible(false)
          // 关闭弹窗时停止轮询
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
        }}
        footer={[
          <Button key="refresh" icon={<ReloadOutlined />} onClick={handleViewProgress}>
            刷新进度
          </Button>,
          <Button key="close" onClick={() => {
            setProgressModalVisible(false)
            // 关闭弹窗时停止轮询
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
              pollIntervalRef.current = null
            }
          }}>
            关闭
          </Button>
        ]}
        width={500}
        closable={true}
      >
        <div style={{ padding: '20px 0' }}>
          <div style={{ marginBottom: 24 }}>
            <Progress
              percent={Math.round(syncProgress.progress || 0)}
              status={getProgressStatus()}
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#87d068',
              }}
            />
          </div>
          
          <Descriptions column={1} size="small">
            <Descriptions.Item label="当前步骤">
              {formatStepName(syncProgress.current_step) || '准备中...'}
            </Descriptions.Item>
            <Descriptions.Item label="状态信息">
              {syncProgress.message || '等待开始...'}
            </Descriptions.Item>
            <Descriptions.Item label="同步状态">
              <Tag color={getProgressStatusColor()}>
                {getProgressStatusText()}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </div>
      </Modal>

      {/* 用户编辑/创建弹窗 */}
      <Modal
        title={userFormMode === 'create' ? '创建用户' : '编辑用户'}
        open={userModalVisible}
        onCancel={() => setUserModalVisible(false)}
        onOk={() => userForm.submit()}
        okText="确认"
        cancelText="取消"
        width={600}
      >
        <Form
          form={userForm}
          layout="vertical"
          onFinish={handleUserSubmit}
        >
          <Form.Item
            label="用户名"
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 50, message: '用户名最多50个字符' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' }
            ]}
          >
            <Input
              placeholder="请输入用户名"
              disabled={userFormMode === 'edit'}
              prefix={<UserOutlined />}
            />
          </Form.Item>

          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' }
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>

          <Form.Item
            label="全名"
            name="full_name"
          >
            <Input placeholder="请输入全名（可选）" />
          </Form.Item>

          {userFormMode === 'create' && (
            <Form.Item
              label="密码"
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6个字符' }
              ]}
            >
              <Input.Password placeholder="请输入密码" />
            </Form.Item>
          )}

          <Form.Item
            label="角色"
            name="role"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色">
              <Select.Option value="user">普通用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="状态"
            name="is_active"
            rules={[{ required: true, message: '请选择状态' }]}
            initialValue={true}
          >
            <Select placeholder="请选择状态">
              <Select.Option value={true}>活跃</Select.Option>
              <Select.Option value={false}>禁用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default AdminDashboard