---
name: jike-scrape
description: 即刻（Jike）MCP 工具集。扫码登录后抓取/发布内容、搜索用户与帖子、评论互动。支持 19 个 MCP 工具，含自动 token 刷新。
---

# Jike MCP 技能

基于 FastMCP 构建的即刻 API 工具，通过 stdio 与 Claude Code 无缝集成。登录一次后 token 自动刷新（~32分钟），无需重复扫码。

---

## 何时使用

用户说：
- `抓取/查看/获取即刻 xxx 的帖子`
- `登录即刻` / `二维码` / `扫码`
- `即刻搜索 xxx`
- `抓取/查看即刻发现页` / `推荐动态`
- `抓取/查看这个帖子的评论`
- `给帖子评论` / `发一条即刻`
- `看看 xxx 的主页` / `关注 xxx`
- `点赞这个帖子`

---

## 核心文件

| 文件 | 作用 |
|------|------|
| `mcp_server.py` | 主程序，19 个工具全部在此 |
| `tokens.json` | 登录 token（含自动刷新） |
| `__init__.py` | 包标记文件 |

---

## 登录流程

### 1. 获取二维码

```
使用 mcp__JikeMCP__get_login_qrcode
```
- 二维码自动保存到临时目录并尝试用浏览器打开
- 返回 `uuid`，用于下一步确认

### 2. 等待扫码确认

```
使用 mcp__JikeMCP__wait_for_login(uuid=上一步的uuid)
```
- 用即刻 App 扫描二维码
- 等待约 2-5 秒，超时 180 秒
- 成功后 token 自动保存到 `tokens.json`

### 3. 检查登录状态

```
使用 mcp__JikeMCP__check_login_status
```
- 返回当前用户名和简介
- Token 过期时自动刷新，无需重新登录

---

## 工具列表（共 19 个）

### 登录相关

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_login_qrcode` | — | 获取登录二维码 |
| `wait_for_login` | `uuid` | 等待扫码确认 |
| `check_login_status` | — | 检查登录状态 |
| `logout` | — | 退出登录，删除 token |

### 内容获取

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_following_feeds_tool` | `load_more_key?` | 关注动态（可翻页） |
| `get_recommend_feeds_tool` | `load_more_key?` | 推荐动态（可翻页） |
| `get_topic_feed_tool` | `topic_id`, `load_more_key?` | 圈子动态（topic_id 从搜索结果获取） |
| `get_user_posts` | `username`, `load_more_key?` | 用户所有帖子（可翻页） |
| `get_post_detail` | `post_id`, `post_type?` | 单条帖子详情 |
| `get_comments` | `target_id`, `target_type?`, `load_more_key?` | 帖子评论（可翻页） |

### 搜索

| 工具 | 参数 | 说明 |
|------|------|------|
| `search` | `keyword`, `load_more_key?` | 搜索帖子、用户、圈子 |

### 用户资料

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_user_profile` | `username` | 获取用户资料（含粉丝/关注/获赞数） |

### 互动操作

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_post_tool` | `content`, `topic_id?` | 发帖 |
| `add_comment` | `target_id`, `content`, `target_type?` | 评论 |
| `like_post` | `post_id`, `target_type?` | 点赞 |
| `unlike_post` | `post_id`, `target_type?` | 取消点赞 |
| `follow_user` | `username` | 关注用户 |
| `unfollow_user` | `username` | 取消关注 |

---

## 使用示例

### 搜索用户帖子

```
username 格式：Jike 用户 UUID（如 72ca4b34-7890-4ca3-bd3b-661e8eb2b3d4）
或主页 URL（如 https://web.okjike.com/u/xxx）
```

步骤：
1. 用 search 工具搜用户名，从结果中获取 username
2. 用 get_user_posts 抓取该用户帖子

### 翻页获取更多内容

API 每页约 25 条，返回结果中的 `load_more_key` 格式为 JSON：
```json
{"lastId": "69dc6688800201ac68d39cd9"}
```

传给工具的 `load_more_key` 参数即可翻页。

### 发帖示例

```
content: "这是一条 Claude Code 发出的测试动态"
topic_id: "59bdc5d8e569780011a4d791"  # 可选，发到指定圈子
```

### 评论示例

```
target_id: 帖子 ID（如 69dfaaae50ac251af897b372）
content: "写得真好！"
target_type: "ORIGINAL_POST"  # 默认，转发帖用 "REPOST"
```

---

## 技术细节

### API 基础

- 基础 URL：`https://api.ruguoapp.com`
- Origin：`https://web.okjike.com`
- Token 放在 HTTP header：`x-jike-access-token`
- Token 有效期约 32 分钟，超时自动刷新

### Token 刷新机制

`_do()` 函数自动处理 401 响应：
1. API 返回 401 → 调用 `_refresh_token()`
2. 用 `refresh_token` 通过 `POST /app_auth_tokens.refresh` 获取新 token
3. 新 token 保存到 `tokens.json`，自动重试原请求
4. 如果 refresh 也失败，提示重新登录

### API 响应结构差异

不同接口返回的 JSON 根字段不同：
- Feed 类（关注/推荐/用户帖子等）：`{"data": [...]}`
- 用户资料：`{"user": {...}}`
- 发帖/评论/互动操作：`{"data": {...}}`

### 用户名解析（resolve_username）

`get_user_profile` / `get_user_posts` 支持多种输入格式：
- UUID：`72ca4b34-7890-4ca3-bd3b-661e8eb2b3d4`（Jike 标准格式）
- 主页 URL：`https://web.okjike.com/u/72ca4b34-...`
- 短码：`okjk.co/xxxx`（需要重定向解析）

---

## 已知问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `check_login_status` 返回"未登录" | Token 过期或响应字段用错 | 重启 MCP 进程让代码生效 |
| `get_user_posts` 返回 400 | username 格式错误或 resolve 失败 | 用搜索获取真实 UUID |
| API 返回 401 | Token 彻底失效 | 重新扫码登录 |
| 分页返回空 | `load_more_key` 格式不对 | 必须是 JSON 字符串 |

---

## 文件结构

```
jike-scrape/
├── SKILL.md          # 本文件
├── README.md         # 原始说明
├── requirements.txt  # 依赖（qrcode, mcp）
└── src/
    ├── mcp_server.py  # 主程序（FastMCP）
    ├── tokens.json    # 登录 token（勿删）
    └── __init__.py
```
