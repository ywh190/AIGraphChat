import React from 'react'
import { Layout, Typography, Space, Button, Avatar, Badge } from 'antd'
import { LogoutOutlined, UserOutlined } from '@ant-design/icons'
import { logout } from '../../services/api'

const { Header } = Layout
const { Title } = Typography

const AppHeader = ({ currentUser, onLogout }) => {
  const handleLogout = () => {
    logout()
    if (onLogout) {
      onLogout()
    }
  }

  return (
    <Header style={{ 
      background: '#001529', 
      padding: '0 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    }}>
      <Title level={3} style={{ color: '#fff', margin: '0', lineHeight: '48px' }}>
        中医药知识图谱系统
      </Title>
      
      {currentUser && (
        <Space size="middle" style={{ color: '#fff' }}>
          <Badge
            status={currentUser.is_active ? 'success' : 'error'}
            text={currentUser.is_active ? '在线' : '离线'}
            style={{ marginRight: 8, color: '#fff' }}
          />
          <span style={{ color: '#fff' }}>{currentUser.username}</span>
          {currentUser.role === 'admin' && (
            <Badge color="blue" text="管理员" style={{ color: '#fff' }} />
          )}
          <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
          <Button 
            type="text" 
            icon={<LogoutOutlined />} 
            onClick={handleLogout}
            style={{ color: '#fff' }}
          >
            登出
          </Button>
        </Space>
      )}
    </Header>
  )
}

export default AppHeader