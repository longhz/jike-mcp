# CLAUDE.md

行为准则，使用 jike-mcp 操作即刻时遵循。

## 准则

### 1. 先确认登录状态

调用任何 API 前，先用 `check_login_status` 确认已登录。
Token 过期（401）时 MCP Server 会自动刷新，无需重新扫码。

### 2. 搜索优先原则

用户提到某个人的帖子时，**先 search，再从结果拿 username**，不要直接猜测。
中文用户名无法用文字输入，必须通过搜索获取其 UUID 格式的 username。

### 3. 翻页说明要清晰

API 每页约 25 条。用 `load_more_key` 翻页时，告诉用户：
- 当前拿了第几页
- 下一页的 key 是什么
- 是否继续翻

### 4. 写操作要二次确认

发帖、评论、点赞/关注等写操作，**先告诉用户要做什么，等确认再执行**。
用户确认后，执行并返回结果。

### 5. ID 要从上下文获取

`post_id`、`username`、`topic_id` 等 ID 从 feed/search 结果中提取，不要自己构造。
如果结果里没有 ID，说明该条目不包含可抓取内容。

### 6. 只做被要求的事

用户说"看看这个帖子"，就只看帖子详情，不要自动翻页或抓评论。
用户说"搜一下"，就只搜一页，不主动翻多页。

---

## 常见任务流程

### 抓某人的帖子
1. `search("关键词")` → 获取 USER_SECTION → 拿到 username
2. `get_user_posts(username)` → 返回第一页
3. 如需翻页，用返回的 `loadMoreKey` 传参

### 找圈子 ID
1. `search("圈子名")` → 获取 TOPIC → 拿到 topic_id
2. `get_topic_feed_tool(topic_id)`

### 互动操作
1. 告诉用户要执行的操作
2. 用户确认后执行
3. 返回结果

---

## 工具索引

| 工具 | 用途 |
|------|------|
| `check_login_status` | 登录检查 |
| `get_login_qrcode` / `wait_for_login` | 登录 |
| `get_following_feeds_tool` | 关注动态 |
| `get_recommend_feeds_tool` | 推荐动态 |
| `get_topic_feed_tool` | 圈子动态 |
| `search` | 搜索（帖子/用户/圈子） |
| `get_user_profile` | 用户资料 |
| `get_user_posts` | 用户帖子 |
| `get_post_detail` | 帖子详情 |
| `get_comments` | 评论 |
| `create_post_tool` | 发帖 |
| `add_comment` | 评论 |
| `like_post` / `unlike_post` | 点赞 |
| `follow_user` / `unfollow_user` | 关注 |
