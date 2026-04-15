# jike-mcp

即刻（Jike）MCP Server — 基于 FastMCP 的 Python 实现，无浏览器抓取与互动工具。

集成到 Claude Code 后可通过自然语言操作即刻：抓取帖子、搜索内容、评论互动等。

## 功能一览

| 类别 | 工具 |
|------|------|
| 登录 | 获取二维码、等待扫码、退出登录 |
| 内容获取 | 关注动态、推荐动态、圈子动态、用户帖子、帖子详情、评论 |
| 搜索 | 帖子/用户/圈子关键词搜索 |
| 用户资料 | 查看用户信息（粉丝/关注/获赞） |
| 互动操作 | 发帖、评论、点赞/取消点赞、关注/取消关注 |

共 **19 个工具**，全部通过 MCP stdio 协议与 AI 助手集成。

## 安装

### 前置依赖

```bash
pip install mcp qrcode
```

### CLAUDE.md（推荐）

复制 `CLAUDE.md` 到项目目录，让 AI 遵循 jike-mcp 使用准则：

```bash
curl -o CLAUDE.md https://raw.githubusercontent.com/longhz/jike-mcp/main/CLAUDE.md
```

### Claude Code MCP 配置

在 `~/.claude.json` 的 `mcpServers` 中添加：

```json
"jike-mcp": {
  "command": "python",
  "args": ["path/to/jike-mcp/src/mcp_server.py"],
  "env": {
    "PYTHONPATH": "path/to/jike-mcp/src"
  }
}
```

重启 Claude Code 即可使用。

## 快速开始

### 1. 登录

```
用户：登录即刻
→ AI 自动调用 get_login_qrcode 获取二维码
→ 用户用即刻 App 扫码
→ AI 调用 wait_for_login(uuid=xxx) 确认
```

### 2. 抓取内容

```
用户：看看哥飞最近的帖子
→ search 搜索「哥飞」→ 获取 username
→ get_user_posts(username) 抓取帖子

用户：获取即刻推荐动态
→ get_recommend_feeds_tool

用户：这个帖子有多少评论
→ get_comments(target_id=帖子ID)
```

### 3. 翻页

API 每页约 25 条，返回结果中的 `load_more_key` 格式为：
```
{"lastId": "69dc6688800201ac68d39cd9"}
```
传给工具的 `load_more_key` 参数即可加载下一页。

### 4. 互动操作

```
用户：给这个帖子点个赞
→ like_post(post_id=xxx)

用户：发一条即刻
→ create_post_tool(content="内容")

用户：评论一下
→ add_comment(target_id=xxx, content="评论内容")
```

## 工具列表

| 工具 | 说明 |
|------|------|
| `check_login_status` | 检查登录状态 |
| `get_login_qrcode` | 获取登录二维码 |
| `wait_for_login` | 等待扫码确认 |
| `logout` | 退出登录 |
| `get_following_feeds_tool` | 关注动态 |
| `get_recommend_feeds_tool` | 推荐动态 |
| `get_topic_feed_tool` | 圈子动态 |
| `search` | 关键词搜索 |
| `get_user_profile` | 用户资料 |
| `get_user_posts` | 用户帖子 |
| `get_post_detail` | 帖子详情 |
| `get_comments` | 帖子评论 |
| `create_post_tool` | 发帖 |
| `add_comment` | 评论 |
| `like_post` | 点赞 |
| `unlike_post` | 取消点赞 |
| `follow_user` | 关注用户 |
| `unfollow_user` | 取消关注 |

## Token 机制

- Token 有效期约 32 分钟
- 过期后 MCP Server 自动调用 `POST /app_auth_tokens.refresh` 刷新
- 刷新后的 token 保存到 `tokens.json`，无需重新扫码
- 彻底失效时提示重新扫码登录

## 文件结构

```
jike-mcp/
├── README.md
├── requirements.txt
├── .gitignore
├── SKILL.md
└── src/
    ├── mcp_server.py   # 主程序
    └── __init__.py
```

`tokens.json` 不会提交到 GitHub（已在 `.gitignore` 中）。

## 技术参考

- API 基础 URL：`https://api.ruguoapp.com`
- 认证：HTTP header `x-jike-access-token`
- 参考项目：[myartings/jikeskill](https://github.com/myartings/jikeskill)（Go 版）
