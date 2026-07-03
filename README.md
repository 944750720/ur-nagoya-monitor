# UR 神奈川空室监控

每天两次自动检查神奈川 UR 团地空房（2 间房及以上），有新房源时通过 Telegram 推送通知。

## 筛选条件

- **地区**：神奈川全县（所有子区域）
- **户型**：2K / 2DK / 2LDK / 3K 及以上（不含 1R、1K、1DK、1LDK）
- **近东京标记**：川崎、横滨北部等区域会在通知中带 ⭐
- **频率**：每天 3 次（08:00 / 14:00 / 20:00 JST）

## 部署步骤

### 1. 创建 Telegram Bot

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示取名
3. 记下 Bot Token（形如 `123456:ABC-DEF...`）

### 2. 获取 Chat ID

1. 给你的 Bot 发一条任意消息
2. 浏览器打开：`https://api.telegram.org/bot<你的TOKEN>/getUpdates`
3. 在返回 JSON 里找到 `"chat":{"id":123456789}`，记下这个数字

### 3. 推送到 GitHub

```bash
cd ur-kanagawa-monitor
git init
git add .
git commit -m "Initial commit: UR Kanagawa monitor"
# 在 GitHub 新建仓库后：
git remote add origin https://github.com/<你的用户名>/ur-kanagawa-monitor.git
git push -u origin main
```

### 4. 配置 Secrets

在 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** 中添加：

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID |

### 5. 启用 Actions

仓库 → **Actions** → 启用 workflows。可手动点 **Run workflow** 测试。

> **首次运行**会建立基线快照，通常不会发通知。从第二次开始，只有**新出现的空房**才会推送。

## 本地测试

```bash
set TELEGRAM_BOT_TOKEN=你的token
set TELEGRAM_CHAT_ID=你的chat_id
python monitor.py
```

## 自定义

编辑 `config.json` 可调整租金、面积下限和请求间隔（秒）。

## 注意

- 仅供个人选房参考，请礼貌使用 UR 接口（默认每区域间隔 2 秒）
- GitHub Actions 定时任务可能有 ±15 分钟延迟
- 数据以 [UR 官网](https://www.ur-net.go.jp/chintai/kanto/kanagawa/list/) 为准
