# 客户话题生成器 Demo

Gradio 网页 + AI 引擎（MiniMax / Claude，均走 Anthropic 兼容协议）。

功能流程：录入客户资料（截图 / 文字）→ AI 提取并建立客户画像 → 生成聊天话题 → 生成候选回复 → 多轮对话陪练。每位客户一份独立存档（`data/customers/<id>.json`）。

## 启动

```powershell
# 1. 建环境（已建过可跳过）
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 配置 Key
copy .env.example .env
# 编辑 .env，填 MINIMAX_API_KEY 和/或 ANTHROPIC_API_KEY

# 3. 连通性测试（可选，第二个参数为测试图片）
.venv\Scripts\python scripts\smoke_test.py
.venv\Scripts\python scripts\smoke_test.py some_screenshot.png

# 4. 启动
.venv\Scripts\python app.py                 # 从 7860 起自动找空闲端口
.venv\Scripts\python app.py --port 8000     # 指定端口
.venv\Scripts\python app.py --share         # 额外生成 gradio.live 公网临时链接
.venv\Scripts\python app.py --host 0.0.0.0  # 局域网可访问
.venv\Scripts\python app.py --open          # 启动后自动打开浏览器
```

实际地址看启动日志的 `Running on local URL`。

## 页面说明

| Tab | 作用 |
|---|---|
| 客户管理 | 列表、新增（姓名 + 标签）、编辑标签、删除（需勾选确认）。点表格某行即切换当前客户 |
| 资料录入 | 上传多张截图 / 粘贴文字，AI 提取客户信息并追加存档；可勾选「提取后立即分析」 |
| 分析页 | 展示客户画像（基本信息 / 性格 / 沟通偏好 / 兴趣 / 痛点 / 关系阶段 / 近期事件 / 禁忌），可重新分析 |
| 话题生成 | 选目的和数量，生成可直接发送的开场白，附理由与注意点；保留历史 |
| 聊天回复 | 粘贴客户消息生成多风格候选回复；下方多轮对话模拟（AI 扮演客户 / AI 做助手），历史按客户保存 |

顶部可切换引擎；「引擎高级设置」可临时覆盖 API Key 和模型名（不写盘），并可勾选是否走 HTTP 代理（地址在 `.env` 的 `PROXY_URL`，`PROXY_ENABLED=true` 则默认勾上）。

## 引擎说明

- **MiniMax Coding Plan**：Anthropic 兼容地址 `https://api.minimaxi.com/anthropic`（海外为 `api.minimax.io`），模型名以控制台为准，默认 `MiniMax-M2.5`。如该模型不支持图片，把 `MINIMAX_SUPPORTS_VISION=false`，图片提取时切换到 Claude。
- **Claude**：需要真实 API Key（`sk-ant-...`）。Claude Code 订阅本身不能直接作为 API Key 使用。
- 调用层只用最小参数集（model / max_tokens / system / messages），不传 thinking 等扩展参数，以兼容第三方兼容层。JSON 结果靠 prompt 约束 + 宽松解析。

## 代码结构

```
app.py          Gradio 入口，顶部引擎/客户选择 + 五个 Tab
config.py       .env 读取、provider 配置
ai_engine.py    anthropic SDK 封装：文本 / 图片 / JSON 解析 / 错误转中文
storage.py      客户 JSON 读写、图片保存、删除
prompts.py      提取 / 画像 / 话题 / 回复 / 扮演 的 prompt
services.py     业务逻辑
ui/             各 Tab 页面
scripts/smoke_test.py  连通性测试
```
