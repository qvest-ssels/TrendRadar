# TrendRadar 项目结构

```
TrendRadar/
├── config/                 # 配置文件目录
│   ├── config.yaml        # 主配置文件
│   └── frequency_words.txt # 关键词频率配置
├── docs/                  # 项目文档
│   └── README.md         # 详细文档
├── mcp_server/          # MCP 服务器实现
│   ├── server.py         # MCP 服务器主文件
│   ├── services/         # 业务逻辑服务
│   │   ├── data_service.py    # 数据服务
│   │   ├── parser_service.py  # 解析服务
│   │   └── cache_service.py   # 缓存服务
│   ├── tools/            # MCP 工具实现
│   │   ├── data_query.py     # 数据查询工具
│   │   ├── analytics.py      # 分析工具
│   │   ├── search_tools.py   # 搜索工具
│   │   ├── config_mgmt.py    # 配置管理工具
│   │   └── system.py         # 系统管理工具
│   └── utils/            # 工具函数
│       ├── date_parser.py    # 日期解析
│       └── errors.py         # 错误处理
├── output/               # 输出目录
│   └── [YYYY年MM月DD日]/    # 按日期组织的输出
│       ├── txt/             # 文本格式数据
│       └── html/            # HTML 报告
├── tests/                # 测试文件
│   ├── test_simple.py       # 基础单元测试
│   ├── conftest.py          # 测试配置
│   └── README.md           # 测试说明
├── main.py               # 主程序入口
├── pyproject.toml        # 项目配置
├── requirements.txt      # 依赖列表
├── Makefile             # 构建脚本
├── pytest.ini           # 测试配置
├── LICENSE              # 许可证
├── README.md            # 项目简介
└── setup-mac.sh         # macOS 安装脚本
```

## 核心文件说明

### 配置文件
- **`config/config.yaml`**: 主配置文件，包含平台设置、时区配置、通知设置等
- **`config/frequency_words.txt`**: 关键词频率词典，用于热点分析

### 核心模块
- **`main.py`**: 主程序，包含数据采集、分析、报告生成等核心逻辑
- **`mcp_server/server.py`**: MCP 服务器实现，提供 AI 助手集成接口

### 服务层
- **`mcp_server/services/`**: 业务逻辑服务
  - `data_service.py`: 数据获取和处理
  - `parser_service.py`: 数据解析和格式化
  - `cache_service.py`: 数据缓存管理

### 工具层
- **`mcp_server/tools/`**: MCP 工具实现
  - `data_query.py`: 新闻数据查询
  - `analytics.py`: 数据分析和趋势预测
  - `search_tools.py`: 智能搜索功能
  - `config_mgmt.py`: 配置管理
  - `system.py`: 系统状态监控

### 测试层
- **`tests/`**: 完整的测试套件
  - 单元测试、集成测试、端到端测试
  - 平台兼容性测试
  - MCP 服务器测试

## 数据流

```
数据源 → main.py → 解析 → 存储 → MCP 服务器 → AI 助手
    ↓         ↓       ↓       ↓         ↓          ↓
平台 API  数据获取  格式化  output/   工具接口   智能分析
RSS 源    缓存机制  去重    数据库    协议转换   趋势预测
```

## 架构特点

- **模块化设计**: 清晰的分层架构，便于维护和扩展
- **插件化平台**: 易于添加新的新闻平台支持
- **标准化接口**: MCP 协议确保与 AI 助手的兼容性
- **可配置化**: 灵活的配置系统支持不同使用场景
- **测试驱动**: 完善的测试覆盖确保代码质量