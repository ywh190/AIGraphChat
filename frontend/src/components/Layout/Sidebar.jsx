import React from 'react'
import { Layout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined,
  MedicineBoxOutlined,
  ExperimentOutlined,
  AppstoreOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  SettingOutlined
} from '@ant-design/icons'
import { isAdmin } from '../../services/api'

const { Sider } = Layout

const AppSidebar = ({ currentUser }) => {
  const navigate = useNavigate()
  const location = useLocation()

  // 基础菜单 - 所有用户都能看到
  const basicMenuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '仪表盘',
      onClick: () => navigate('/')
    },
    {
      key: '/prescriptions',
      icon: <MedicineBoxOutlined />,
      label: '方剂',
      onClick: () => navigate('/prescriptions')
    },
    {
      key: '/herbs',
      icon: <ExperimentOutlined />,
      label: '药材',
      onClick: () => navigate('/herbs')
    },
    {
      key: '/medics',
      icon: <AppstoreOutlined />,
      label: '中成药',
      onClick: () => navigate('/medics')
    },
    {
      key: '/knowledge-graph',
      icon: <NodeIndexOutlined />,
      label: '知识图谱',
      onClick: () => navigate('/knowledge-graph')
    },
    {
      key: '/ai-chat',
      icon: <RobotOutlined />,
      label: 'AI智能问答',
      onClick: () => navigate('/ai-chat')
    },

  ]

  // 管理员专用菜单
  const adminMenuItems = [
    {
      type: 'divider'
    },
    {
      key: '/admin',
      icon: <SettingOutlined />,
      label: '系统管理',
      onClick: () => navigate('/admin')
    }
  ]

  // 根据用户角色组合菜单
  const menuItems = [
    ...basicMenuItems,
    ...(currentUser && isAdmin() ? adminMenuItems : [])
  ]

  return (
    <Sider width={200} style={{ background: '#fff' }}>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        style={{ height: '100%', borderRight: 0 }}
        items={menuItems}
      />
    </Sider>
  )
}

export default AppSidebar