# -*- coding: utf-8 -*-
"""
Jike MCP Server — Python Implementation
基于 myartings/jikeskill Go 版完全重写
端口: 19999 (用户指定高端口)
使用 FastMCP，urllib.request (无 requests 依赖)
"""

import os
import sys
import json
import time
import base64
import shutil
import tempfile
import argparse
import urllib.request
import urllib.error
import urllib.parse
import re
import webbrowser
from pathlib import Path

# Resolve skill dir
SKILL_DIR = Path(__file__).parent
TOKENS_FILE = SKILL_DIR / "tokens.json"


# ─────────────────────────────────────────────────────────────────────────────
# Token Storage (对齐 Go tokens.Store)
# ─────────────────────────────────────────────────────────────────────────────

def load_tokens() -> dict | None:
    if not TOKENS_FILE.exists():
        return None
    try:
        with open(TOKENS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("access_token"):
            return data
    except Exception:
        pass
    return None


def save_tokens(access_token: str, refresh_token: str = "", username: str = ""):
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump({"access_token": access_token, "refresh_token": refresh_token, "username": username}, f, indent=2)


def delete_tokens():
    if TOKENS_FILE.exists():
        TOKENS_FILE.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Client (对齐 Go http.Client + urllib.request)
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.ruguoapp.com"
ORIGIN = "https://web.okjike.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _req(method: str, path: str, token: str = "", body: dict = None) -> tuple[int, dict, bytes]:
    """返回 (status_code, headers_dict, body_bytes)。"""
    url = BASE_URL + path
    headers = {
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["x-jike-access-token"] = token

    data = None
    if body is not None:
        data = json.dumps(body).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, resp_headers, resp.read()
    except urllib.error.HTTPError as e:
        resp_headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, resp_headers, e.read()


def _refresh_token() -> bool:
    """刷新 access token。成功返回 True，失败返回 False。"""
    td = load_tokens()
    if not td or not td.get("refresh_token"):
        return False
    url = BASE_URL + "/app_auth_tokens.refresh"
    headers = {
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "User-Agent": UA,
        "Content-Type": "application/json",
        "x-jike-refresh-token": td["refresh_token"],
    }
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_access = resp.headers.get("x-jike-access-token", "")
            new_refresh = resp.headers.get("x-jike-refresh-token", "")
            if not new_access:
                return False
            save_tokens(new_access, new_refresh or td.get("refresh_token", ""), td.get("username", ""))
            return True
    except Exception:
        return False


def _do(path: str, token: str = "", body: dict = None) -> dict:
    """POST/GET 返回解析后的 JSON dict。"""
    method = "POST" if body is not None else "GET"
    status, _, raw = _req(method, path, token, body)
    # 401 → 尝试刷新 token 重试一次
    if status == 401 and _refresh_token():
        td = load_tokens()
        status, _, raw = _req(method, path, td["access_token"] if td else "", body)
    if status >= 400:
        raise RuntimeError(f"API error {status}: {raw[:200]}")
    if not raw:
        raise RuntimeError(f"API returned empty response for {path}")
    return json.loads(raw)


def _do_authed(path: str, body: dict = None) -> dict:
    """带认证的请求，自动处理 401 refresh。"""
    td = load_tokens()
    token = td["access_token"] if td else ""
    result = _do(path, token, body)
    # 如果 401，尝试 refresh
    # (简化版：直接返回结果，MCP tool 会提示重新登录)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Login / QR Code
# ─────────────────────────────────────────────────────────────────────────────

def create_session() -> str:
    status, _, raw = _req("POST", "/sessions.create")
    if status != 200:
        raise RuntimeError(f"sessions.create failed: {status}")
    data = json.loads(raw)
    uuid = data.get("uuid", "")
    if not uuid:
        raise RuntimeError(f"Empty UUID: {raw}")
    return uuid


def generate_qr(uuid: str) -> str:
    """生成 QR 码，返回 base64 PNG。"""
    try:
        import qrcode as qr
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "qrcode[pil]"])
        import qrcode as qr

    scan_url = f"https://www.okjike.com/account/scan?uuid={uuid}"
    deep_link = (
        f"jike://page.jk/web?url="
        f"https%3A%2F%2Fwww.okjike.com%2Faccount%2Fscan%3Fuuid%3D{uuid}"
        f"%26displayHeader%3Dfalse%26displayFooter%3Dfalse"
    )
    q = qr.QRCode(version=8, error_correction=qr.ERROR_CORRECT_M, box_size=10, border=4)
    q.add_data(deep_link)
    q.make(fit=True)
    img = q.make_image(fill_color="black", back_color="white")

    buf = __import__("io").BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def wait_login(uuid: str, timeout: int = 180) -> dict:
    """轮询等待扫码确认，返回 user dict。"""
    url = f"/sessions.wait_for_confirmation?uuid={uuid}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _, raw = _req("GET", url)
        if status == 200:
            data = json.loads(raw)
            access_token = data.get("x-jike-access-token", "")
            refresh_token = data.get("x-jike-refresh-token", "")
            if data.get("confirmed") and access_token:
                save_tokens(access_token, refresh_token)
                # 获取用户信息
                user_resp = _do("/1.0/users/profile?username=", access_token)
                user = user_resp.get("user", {})  # 注意：profile 返回 {"user": {...}}
                if user.get("username"):
                    save_tokens(access_token, refresh_token, user.get("username", ""))
                return user
        elif status == 404:
            raise RuntimeError("Session expired — please get a new QR code")
        time.sleep(2)
    raise TimeoutError("Login timeout")


def _check_login_status() -> tuple[bool, dict | None]:
    td = load_tokens()
    if not td or not td.get("access_token"):
        return False, None
    try:
        resp = _do("/1.0/users/profile?username=", td["access_token"])
        # /1.0/users/profile?username= 返回 {"user": {...}} (空用户名=当前用户)
        user = resp.get("user", {})
        if user.get("username"):
            # 顺便更新 username
            save_tokens(td["access_token"], td.get("refresh_token", ""), user.get("username", ""))
            return True, user
    except Exception:
        pass
    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# URL 解析 (对齐 Go resolve.go)
# ─────────────────────────────────────────────────────────────────────────────

def resolve_username(raw: str) -> str:
    """解析即刻短 URL / 主页 URL，返回 username。"""
    # UUID 格式直接返回（包含很多横杠，不可能是短码）
    if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-', raw, re.I):
        return raw
    # 处理 bare short code (4-10 字母数字，混合大小写)
    if (4 <= len(raw) <= 10 and "/" not in raw and "." not in raw
            and re.match(r'^[A-Za-z0-9]+$', raw)
            and re.search(r'[A-Z]', raw) and re.search(r'[a-z]', raw)):
        raw = f"https://okjk.co/{raw}"
    if "://" not in raw:
        raw = "https://" + raw

    # 手动跟随重定向链
    current = raw
    client = urllib.request.OpenerDirector()
    for _ in range(10):
        try:
            req = urllib.request.Request(current, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                loc = resp.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            status = e.code
            loc = e.headers.get("Location", "")
        except Exception:
            break

        u = _extract_username(current)
        if u:
            return u

        if 300 <= status < 400 and loc:
            current = loc
            continue
        break

    u = _extract_username(current)
    if u:
        return u
    # 无法解析，直接返回原始输入
    return raw


def _extract_username(url: str) -> str:
    for pattern in ["okjike.com/u/", "okjike.com/users/"]:
        idx = url.find(pattern)
        if idx >= 0:
            rest = url[idx + len(pattern):]
            for sep in "/?#":
                p = rest.find(sep)
                if p >= 0:
                    rest = rest[:p]
            if rest:
                return rest
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# API 操作
# ─────────────────────────────────────────────────────────────────────────────

def get_following_feeds(load_more_key=None):
    body = {}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/personalUpdate/followingUpdates", _token(), body)


def get_recommend_feeds(load_more_key=None):
    body = {}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/recommendFeed/list", _token(), body)


def _get_topic_feed(topic_id, load_more_key=None):
    body = {"topicId": topic_id}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/topicFeed/list", _token(), body)


def _search(keyword, load_more_key=None):
    body = {"keywords": keyword, "type": "ALL"}
    if load_more_key:
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/search/integrate", _token(), body)


def _get_post_detail(post_id, post_type="ORIGINAL_POST"):
    path = "/1.0/reposts/get" if post_type == "REPOST" else "/1.0/originalPosts/get"
    # GET with query param
    return _do(f"{path}?id={post_id}", _token())


def _create_post(content, topic_id="", picture_keys=None):
    body = {"content": content}
    if topic_id:
        body["topicId"] = topic_id
    if picture_keys:
        body["pictureKeys"] = picture_keys
    return _do("/1.0/originalPosts/create", _token(), body)


def _get_comments(target_id, target_type="ORIGINAL_POST", load_more_key=None):
    body = {"targetId": target_id, "targetType": target_type}
    if load_more_key:
        if isinstance(load_more_key, str):
            load_more_key = json.loads(load_more_key)
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/comments/listPrimary", _token(), body)


def _add_comment(target_id, target_type="ORIGINAL_POST", content=""):
    return _do("/1.0/comments/add", _token(),
                {"targetId": target_id, "targetType": target_type, "content": content})


def _get_user_profile(username):
    username = resolve_username(username)
    return _do(f"/1.0/users/profile?username={urllib.parse.quote(username)}", _token())


def _get_user_posts(username, load_more_key=None):
    username = resolve_username(username)
    body = {"username": username}
    if load_more_key:
        # MCP 传过来的是 JSON 字符串，需要 parse 回对象
        if isinstance(load_more_key, str):
            load_more_key = json.loads(load_more_key)
        body["loadMoreKey"] = load_more_key
    return _do("/1.0/personalUpdate/single", _token(), body)


def _like_post(post_id, target_type="ORIGINAL_POST"):
    return _do("/1.0/likes/save", _token(),
                {"targetId": post_id, "targetType": target_type})


def _unlike_post(post_id, target_type="ORIGINAL_POST"):
    return _do("/1.0/likes/remove", _token(),
               {"targetId": post_id, "targetType": target_type})


def _follow_user(username):
    return _do("/1.0/userRelation/follow", _token(), {"username": username})


def _unfollow_user(username):
    return _do("/1.0/userRelation/unfollow", _token(), {"username": username})


def _token() -> str:
    td = load_tokens()
    return td["access_token"] if td else ""


# ─────────────────────────────────────────────────────────────────────────────
# FastMCP Server
# ─────────────────────────────────────────────────────────────────────────────

def build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "mcp[fastapi]"])
        from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("jike-mcp")

    # ── Auth ──────────────────────────────────────────────────────────────

    @mcp.tool()
    def check_login_status() -> str:
        """检查当前是否已登录即刻。"""
        logged_in, user = _check_login_status()
        if logged_in and user:
            return f"已登录: {user.get('screenName','')} (@{user.get('username','')})\n简介: {user.get('briefIntro','')}"
        return "未登录。请使用 get_login_qrcode 获取二维码扫码登录。"

    @mcp.tool()
    def get_login_qrcode() -> dict:
        """获取登录二维码（返回 base64 PNG 图片）。"""
        uuid = create_session()
        qr_b64 = generate_qr(uuid)
        # 保存到临时文件并尝试打开
        qr_path = Path(tempfile.gettempdir()) / "jike_qr.png"
        qr_path.write_bytes(base64.b64decode(qr_b64))
        try:
            webbrowser.open(f"file://{qr_path}")
        except Exception:
            pass
        return {
            "uuid": uuid,
            "qrcode_base64": qr_b64,
            "qr_path": str(qr_path),
            "message": f"二维码已保存到: {qr_path}\n请用即刻 App 扫码确认。\n扫码后调用 wait_for_login 工具，传入 uuid 参数。",
        }

    @mcp.tool()
    def wait_for_login(uuid: str) -> str:
        """等待扫码确认。uuid 来自 get_login_qrcode 的返回值。"""
        try:
            user = wait_login(uuid)
            return (f"登录成功！\n"
                    f"用户: {user.get('screenName','')} (@{user.get('username','')})\n"
                    f"简介: {user.get('briefIntro','')}")
        except TimeoutError:
            return "登录超时，请重新获取二维码。"
        except Exception as e:
            return f"登录失败: {e}"

    @mcp.tool()
    def logout() -> str:
        """退出登录，删除存储的 token。"""
        delete_tokens()
        return "已退出登录。"

    # ── Feeds ─────────────────────────────────────────────────────────────

    @mcp.tool()
    def get_following_feeds_tool(load_more_key: str = None) -> str:
        """获取关注动态。"""
        resp = get_following_feeds(load_more_key)
        return _format_posts(resp.get("data", []))

    @mcp.tool()
    def get_recommend_feeds_tool(load_more_key: str = None) -> str:
        """获取推荐动态。"""
        resp = get_recommend_feeds(load_more_key)
        return _format_posts(resp.get("data", []))

    @mcp.tool()
    def get_topic_feed_tool(topic_id: str, load_more_key: str = None) -> str:
        """获取圈子动态。topic_id 从搜索结果中获取。"""
        resp = _get_topic_feed(topic_id, load_more_key)
        return _format_posts(resp.get("data", []))

    # ── Search ────────────────────────────────────────────────────────────

    @mcp.tool()
    def search(keyword: str, load_more_key: str = None) -> str:
        """搜索帖子、用户、圈子。"""
        resp = _search(keyword, load_more_key)
        lines = [f"搜索「{keyword}」结果:"]
        for item in resp.get("data", []):
            t = item.get("type", "")
            if t in ("SECTION_HEADER", "SECTION_FOOTER", "USER_SECTION"):
                continue
            u = item.get("user", {})
            content = item.get("content", "")
            if t == "TOPIC":
                lines.append(f"  [圈子] {content}  ID: {item.get('id','')}")
            elif content:
                lines.append(f"  [{u.get('screenName','?')}] {content[:100]}")
                lines.append(f"    ID: {item.get('id','')} 👍{item.get('likeCount',0)} 💬{item.get('commentCount',0)}")
            lines.append("")
        return "\n".join(lines) if lines else "未找到结果。"

    # ── Posts ────────────────────────────────────────────────────────────

    @mcp.tool()
    def get_post_detail(post_id: str, post_type: str = "ORIGINAL_POST") -> str:
        """获取帖子详情。"""
        resp = _get_post_detail(post_id, post_type)
        data = resp.get("data", {})
        if not data:
            return f"未找到帖子: {post_id}"
        u = data.get("user", {})
        return (f"[{u.get('screenName','?')} (@{u.get('username','')}))]\n"
                f"{data.get('content','')}\n"
                f"👍{data.get('likeCount',0)} 💬{data.get('commentCount',0)} 🔁{data.get('repostCount',0)}")

    @mcp.tool()
    def create_post_tool(content: str, topic_id: str = "") -> str:
        """发帖子。"""
        resp = _create_post(content, topic_id)
        data = resp.get("data", {})
        if data.get("id"):
            return f"发布成功！ID: {data['id']}"
        return f"发布结果: {json.dumps(resp, ensure_ascii=False, indent=2)}"

    # ── Comments ─────────────────────────────────────────────────────────

    @mcp.tool()
    def get_comments(target_id: str, target_type: str = "ORIGINAL_POST") -> str:
        """获取帖子评论。"""
        resp = _get_comments(target_id, target_type)
        lines = ["评论:"]
        for c in resp.get("data", []):
            u = c.get("user", {})
            lines.append(f"[{u.get('screenName','?')}] {c.get('content','')}")
            lines.append(f"  👍{c.get('likeCount',0)}  {c.get('createdAt','')}")
        return "\n".join(lines) if lines else "暂无评论。"

    @mcp.tool()
    def add_comment(target_id: str, content: str, target_type: str = "ORIGINAL_POST") -> str:
        """评论帖子。"""
        resp = _add_comment(target_id, target_type, content)
        data = resp.get("data", {})
        if data.get("id"):
            return f"评论成功！"
        return f"评论结果: {json.dumps(resp, ensure_ascii=False, indent=2)}"

    # ── User ─────────────────────────────────────────────────────────────

    @mcp.tool()
    def get_user_profile(username: str) -> str:
        """获取用户资料。接受 username 或主页 URL。"""
        resp = _get_user_profile(username)
        data = resp.get("user", {})   # profile API 返回 {"user": {...}}
        if not data:
            return f"未找到用户: {username}"
        s = data.get("statsCount", {}) or {}
        sn = data.get("screenName", "")
        un = data.get("username", "")
        bio = data.get("briefIntro", "") or data.get("bio", "")
        return (f"{sn} (@{un})\n"
                f"简介: {bio}\n"
                f"关注: {s.get('followingCount',0)}  粉丝: {s.get('followedCount',0)}  获赞: {s.get('liked',0)}")

    @mcp.tool()
    def get_user_posts(username: str, load_more_key: str = None) -> str:
        """获取用户帖子。"""
        resp = _get_user_posts(username, load_more_key)
        return _format_posts(resp.get("data", []))

    # ── Interactions ────────────────────────────────────────────────────

    @mcp.tool()
    def like_post(post_id: str, target_type: str = "ORIGINAL_POST") -> str:
        """点赞帖子。"""
        _like_post(post_id, target_type)
        return "已点赞！"

    @mcp.tool()
    def unlike_post(post_id: str, target_type: str = "ORIGINAL_POST") -> str:
        """取消点赞。"""
        _unlike_post(post_id, target_type)
        return "已取消点赞。"

    @mcp.tool()
    def follow_user(username: str) -> str:
        """关注用户。"""
        _follow_user(username)
        return f"已关注 @{username}"

    @mcp.tool()
    def unfollow_user(username: str) -> str:
        """取消关注。"""
        _unfollow_user(username)
        return f"已取消关注 @{username}"

    return mcp


def _format_posts(posts: list) -> str:
    """格式化帖子列表为易读文本。"""
    if not posts:
        return "暂无内容。"
    lines = []
    for p in posts:
        u = p.get("user", {})
        topic = p.get("topic") or {}
        topic_name = topic.get("content", "") if isinstance(topic, dict) else ""
        content = p.get("content", "").replace("\n", " ")[:120]
        t = f"  #{topic_name}" if topic_name else ""
        lines.append(f"[{u.get('screenName','?')}] {content}{t}")
        lines.append(f"  👍{p.get('likeCount',0)} 💬{p.get('commentCount',0)} 🔁{p.get('repostCount',0)}  ID:{p.get('id','')}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jike MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http"], default="stdio",
                        help="stdio: Claude Code integration; http: standalone REST API")
    parser.add_argument("--port", type=int, default=19999, help="HTTP 端口 (默认 19999)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="HTTP 主机 (默认 127.0.0.1)")
    args = parser.parse_args()

    print(f"启动 Jike MCP Server (mode={args.mode}, port={args.port})...", file=sys.stderr)

    mcp = build_mcp()

    if args.mode == "stdio":
        # Claude Code integration via stdio
        mcp.run(transport="stdio")
    else:
        # Standalone HTTP server
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
