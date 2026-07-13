# UR 名古屋空室监控

每天 3 次自动检查名古屋 UR 团地空房（2 间房及以上），有新房源时通过 Telegram 推送通知。

## 筛选条件

- **地区**：名古屋市全部 15 个有 UR 房源的区（南区无 UR 团地）
- **户型**：2K / 2DK / 2LDK / 3K 及以上（不含 1R、1K、1DK、1LDK）
- **市中心标记**：中区、東区、中村区、千種区、昭和区、熱田区会在通知中带 ⭐
- **频率**：每天 3 次（08:00 / 14:00 / 20:00 JST），由 [cron-job.org](https://cron-job.org) 免费触发

## 部署步骤

### 1. 创建 Telegram Bot

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`，按提示取名
3. 记下 Bot Token（形如 `123456:ABC-DEF...`）

### 2. 获取 Chat ID

1. 给你的 Bot 发一条任意消息
2. 浏览器打开：`https://api.telegram.org/bot<你的TOKEN>/getUpdates`
3. 在返回 JSON 里找到 `"chat":{"id":123456789}`，记下这个数字

### 3. 配置 GitHub Secrets

在 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** 中添加：

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID |

### 4. 配置 cron-job.org 定时触发（免费）

GitHub 内置 cron 延迟可达数小时，因此改用 **cron-job.org** 在指定 JST 时间触发 workflow。

#### 4.1 创建 GitHub Personal Access Token

1. 打开 [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)** 或 Fine-grained token
3. 权限至少包含：**repo**（classic）或 **Actions: Read and write**（fine-grained，仅限本仓库）
4. 生成后复制 Token（只显示一次）

#### 4.2 注册 cron-job.org

1. 打开 [https://cron-job.org](https://cron-job.org) 注册免费账号
2. 进入 **Cronjobs** → **Create cronjob**

#### 4.3 创建 3 个定时任务

每个任务配置相同，只有 **Schedule** 时间不同：

| 字段 | 值 |
|------|-----|
| Title | `UR Monitor 08:00`（14:00 / 20:00 各建一个） |
| URL | `https://api.github.com/repos/944750720/ur-nagoya-monitor/actions/workflows/monitor.yml/dispatches` |
| Schedule | 自定义 → 时区选 **Asia/Tokyo** → 分别设为 `08:00`、`14:00`、`20:00` 每天 |
| Request method | **POST** |
| Request body | `{"ref":"main"}` |
| Headers | 见下方 |

**Headers（两个都要加）：**

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <你的GitHub PAT>` |
| `Accept` | `application/vnd.github+json` |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

> cron-job.org 免费版足够个人使用（每天 3 次远低于限额）。

#### 4.4 验证

1. 在 cron-job.org 点 **Run now** 测试
2. 到 GitHub **Actions** 页面，应看到新的 workflow run
3. 首次运行建立基线，通常不发 Telegram；第二次起才推送新空房

### 5. 手动测试

仓库 → **Actions** → **UR Nagoya Monitor** → **Run workflow**

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
- GitHub PAT 和 Telegram Token 只存在 cron-job.org / GitHub Secrets，不要提交到仓库
- 数据以 [UR 官网](https://www.ur-net.go.jp/chintai/tokai/aichi/list/) 为准
