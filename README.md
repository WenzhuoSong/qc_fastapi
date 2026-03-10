# CrewAI + FastAPI Project Framework

An intelligent agent API service framework based on CrewAI and FastAPI, supporting the creation and management of AI agent teams to execute complex tasks.

## Project Structure

```
qc_fastapi/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── crew.py          # CrewAI related APIs
│   │       │   ├── health.py        # Health checks
│   │       │   └── tasks.py         # Task management
│   │       └── router.py            # Route aggregation
│   ├── core/
│   │   └── tools.py                 # Custom tools
│   ├── services/
│   │   └── crew_service.py          # CrewAI service layer
│   ├── config.py                    # Application configuration
│   └── main.py                      # FastAPI main application
├── tests/                           # Test files
├── requirements.txt                 # Dependency management
├── run.py                          # Startup script
├── example_usage.py                # Usage examples
└── README.md                       # Project documentation
```

## Prerequisites

- **Python**: 3.10, 3.11, 3.12, or 3.13 (3.11 recommended)
- **pip**: 21.0 or higher
- **Virtual Environment**: Recommended (venv or conda)

> **Note**: Python 3.14+ is not yet fully supported by all dependencies (e.g., numpy, crewai). Please use Python 3.10-3.13 for full functionality.

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy environment template
cp env_example.txt .env

# Edit .env file and set your OpenAI API Key
OPENAI_API_KEY=your_api_key_here
```

### 3. Start the Service

```bash
# Development mode (with hot reload)
python run.py

# Or start directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

After starting, access:
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## API Endpoints

### Health Check

```bash
GET /health
GET /api/v1/health/
```

### CrewAI Agents

```bash
# Get Crew information
GET /api/v1/crew/info

# List available agents
GET /api/v1/crew/agents

# Execute Crew task
POST /api/v1/crew/execute
Content-Type: application/json

{
    "topic": "Applications of AI in Healthcare"
}
```

### Task Management

```bash
# Create task
POST /api/v1/tasks/
Content-Type: application/json

{
    "name": "Research Task",
    "description": "Research latest advances in quantum computing",
    "agent_role": "Researcher",
    "expected_output": "A research report"
}

# List all tasks
GET /api/v1/tasks/

# Get task details
GET /api/v1/tasks/{task_id}

# Delete task
DELETE /api/v1/tasks/{task_id}
```

## Usage Examples

### Python Client Example

```python
import requests

# Execute Crew task
response = requests.post(
    "http://localhost:8000/api/v1/crew/execute",
    json={"topic": "Applications of AI in Healthcare"},
    timeout=300
)

result = response.json()
print(result["result"])
```

### Command Line Example

```bash
# Get Crew information
python example_usage.py crew_info

# Execute Crew task
python example_usage.py execute

# Task management example
python example_usage.py tasks
```

## Default Agent Team

The project includes a pre-configured content creation team with three agents:

1. **Researcher** - Conducts in-depth research on specified topics, collecting comprehensive and accurate information
2. **Content Writer** - Transforms research content into high-quality, readable articles
3. **Editor** - Reviews content quality to ensure accuracy and consistency

## Custom Configuration

### Custom Agents

Modify the `_create_default_agents` method in `app/services/crew_service.py`:

```python
def _create_default_agents(self) -> List[Agent]:
    custom_agent = Agent(
        role="Data Analyst",
        goal="Analyze data and provide insights",
        backstory="You are an experienced data analyst...",
        verbose=True,
        allow_delegation=False,
    )
    return [custom_agent]
```

### Custom Tasks

Modify the `_create_default_tasks` method:

```python
def _create_default_tasks(self) -> List[Task]:
    custom_task = Task(
        description="Analyze data for {topic}",
        expected_output="Data analysis report",
        agent=self.default_agents[0],
    )
    return [custom_task]
```

## Development

### Run Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
```

## Deployment

### Railway Deployment (Recommended)

本项目已配置好 Docker 支持，可一键部署到 Railway：

#### 1. 准备工作

确保已安装 [Railway CLI](https://docs.railway.app/develop/cli) 并登录：

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login
```

#### 2. 部署步骤

```bash
# 进入项目目录
cd qc_fastapi

# 初始化 Railway 项目
railway init

# 设置环境变量（必需）
railway variables set OPENAI_API_KEY=your_api_key_here

# 部署
railway up
```

#### 3. 环境变量配置

在 Railway Dashboard 或 CLI 中设置以下变量：

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | ✅ 是 |
| `APP_NAME` | 应用名称 | ❌ 否（默认：CrewAI FastAPI Service） |
| `DEBUG` | 调试模式 | ❌ 否（默认：false） |

#### 4. 查看部署状态

```bash
# 查看部署日志
railway logs

# 打开部署后的网站
railway open
```

#### 5. 自动部署

连接 GitHub 仓库到 Railway 可实现自动部署：
1. 在 Railway Dashboard 中选择项目
2. 点击 Settings → Source
3. 连接 GitHub 仓库
4. 启用 Auto Deploy

### Docker 本地测试

```bash
# 构建镜像
docker build -t qc-fastapi .

# 运行容器
docker run -p 8000:8000 -e OPENAI_API_KEY=your_key qc-fastapi

# 访问 http://localhost:8000/docs
```

## Tech Stack

- **FastAPI** - Modern, fast web framework
- **CrewAI** - AI agent orchestration framework
- **Pydantic** - Data validation and settings management
- **Uvicorn** - ASGI server

## License

MIT License
