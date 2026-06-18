import React, { useState } from 'react'
import { Card, Form, Input, Button, message, Divider } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import api, { getCurrentUser } from '../services/api'
import './Login.css'

const Login = ({ onLogin }) => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [loginSuccess, setLoginSuccess] = useState(false)

  const onFinish = async (values) => {
    // 防止重复点击
    if (loading || loginSuccess) return
    
    setLoading(true)
    try {
      // 使用application/x-www-form-urlencoded格式提交登录请求
      const response = await api.post('/auth/login', 
        new URLSearchParams({
          username: values.username,
          password: values.password
        }).toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }
      )
      
      // 标记登录成功
      setLoginSuccess(true)
      
      // 保存token和用户信息到localStorage
      localStorage.setItem('token', response.access_token)
      localStorage.setItem('user', JSON.stringify(response.user))
      
      // 更新API请求的认证头
      api.defaults.headers.common['Authorization'] = `Bearer ${response.access_token}`
      
      // 显示成功消息
      message.success('登录成功')
      
      // 传递用户信息给父组件
      if (onLogin) {
        onLogin(response.user)
      }
      
      // 延迟跳转，确保状态更新完成
      setTimeout(() => {
        navigate('/', { replace: true })
      }, 500)
    } catch (error) {
      console.error('Login error:', error)
      // 处理错误消息
      const errorMessage = error.response?.data?.detail || 
                          (error.response?.data?.errors ? 
                           Object.values(error.response.data.errors).join(', ') : 
                           '登录失败，请检查用户名和密码')
      message.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-container">
      <Card className="login-card">
        <h2 className="login-title">系统登录</h2>
        <Divider />
        <Form
          name="login"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名！' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码！' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
          <div className="login-footer">
            <p>默认管理员账户：admin / admin123</p>
            <p>测试用户账户：testuser / 123456</p>
            <p>还没有账户？<a onClick={() => navigate('/register')}>立即注册</a></p>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default Login