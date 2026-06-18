@echo off
echo === 中医药知识图谱系统启动 ===

REM 检查Docker是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 请先安装Docker
    pause
    exit /b 1
)

REM 检查Docker Compose是否安装
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 请先安装Docker Compose
    pause
    exit /b 1
)

echo 1. 启动数据库服务...
docker-compose up -d mysql neo4j

echo 等待数据库启动...
timeout /t 30 /nobreak

echo 2. 启动后端服务...
docker-compose up -d backend

echo 3. 启动前端服务...
docker-compose up -d frontend

echo 4. 数据导入...
echo 等待后端服务启动...
timeout /t 10 /nobreak

echo 开始数据导入...
docker-compose exec backend python scripts/data_import.py

echo === 启动完成 ===
echo 后端API: http://localhost:10001
echo 前端应用: http://localhost:3000
echo Neo4j浏览器: http://localhost:7474
echo MySQL: localhost:3306
echo.
echo 使用 'docker-compose logs -f' 查看日志
echo 使用 'docker-compose down' 停止服务

pause