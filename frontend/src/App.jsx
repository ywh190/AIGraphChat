import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Layout } from 'antd'
import Header from './components/Layout/Header'
import Sidebar from './components/Layout/Sidebar'
import Dashboard from './pages/Dashboard'
import Prescriptions from './pages/Prescriptions'
import Herbs from './pages/Herbs'
import Medics from './pages/Medics'
import KnowledgeGraph from './pages/KnowledgeGraph'
import AIChat from './pages/AIChat'
import Search from './pages/Search'
import Login from './pages/Login'
import Register from './pages/Register'
import AdminDashboard from './pages/AdminDashboard'
import { getCurrentUser, isAdmin } from './services/api'
import './App.css'

const { Content } = Layout

function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const location = useLocation()

  // 从localStorage加载用户信息
  useEffect(() => {
    const loadUser = () => {
      const token = localStorage.getItem('token')
      const user = getCurrentUser()
      
      console.log('App初始化 - token:', token ? '存在' : '不存在')
      console.log('App初始化 - user:', user)
      
      if (token && user) {
        setCurrentUser(user)
      } else {
        setCurrentUser(null)
      }
      setLoading(false)
    }

    loadUser()
  }, [])

  // 登录后更新用户信息
  const handleLogin = (user) => {
    setCurrentUser(user)
  }

  // 登出后清除用户信息
  const handleLogout = () => {
    setCurrentUser(null)
  }

  // 保护路由组件
  const ProtectedRoute = ({ element }) => {
    if (loading) {
      return <div>加载中...</div>
    }
    
    // 检查localStorage中是否有token，如果有则认为用户已登录
    const token = localStorage.getItem('token')
    const isAuthenticated = currentUser || token
    
    return isAuthenticated ? element : <Navigate to="/login" replace />
  }

  // 管理员专用路由组件
  const AdminRoute = ({ element }) => {
    if (loading) {
      return <div>加载中...</div>
    }
    
    // 直接从localStorage获取用户信息进行检查
    const userStr = localStorage.getItem('user')
    let userIsAdmin = false
    
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        userIsAdmin = user.role === 'admin' || user.role === 'ADMIN' || 
                     (user.role?.value === 'admin' || user.role?.value === 'ADMIN')
      } catch (e) {
        console.error('解析用户信息失败:', e)
      }
    }
    
    // 检查是否已登录
    const isAuthenticated = currentUser || localStorage.getItem('token')
    
    // 如果未登录，重定向到登录页
    if (!isAuthenticated) {
      return <Navigate to="/login" replace />
    }
    
    // 如果已登录但不是管理员，重定向到首页
    if (!userIsAdmin) {
      return <Navigate to="/" replace />
    }
    
    // 管理员可以访问
    return element
  }

  // 登录和注册页面不需要布局
  if (location.pathname === '/login') {
    return <Login onLogin={handleLogin} />
  }
  
  if (location.pathname === '/register') {
    return <Register />
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header currentUser={currentUser} onLogout={handleLogout} />
      <Layout>
        <Sidebar currentUser={currentUser} />
        <Layout style={{ padding: '24px' }}>
          <Content>
            <Routes>
              <Route path="/" element={<ProtectedRoute element={<Dashboard />} />} />
              <Route path="/prescriptions" element={<ProtectedRoute element={<Prescriptions />} />} />
              <Route path="/herbs" element={<ProtectedRoute element={<Herbs />} />} />
              <Route path="/medics" element={<ProtectedRoute element={<Medics />} />} />
              <Route path="/knowledge-graph" element={<ProtectedRoute element={<KnowledgeGraph />} />} />
              <Route path="/ai-chat" element={<ProtectedRoute element={<AIChat />} />} />
              <Route path="/search" element={<ProtectedRoute element={<Search />} />} />
              <Route path="/register" element={<Register />} />
              
              {/* 管理员专用路由 */}
              <Route path="/admin" element={<AdminRoute element={<AdminDashboard />} />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default App