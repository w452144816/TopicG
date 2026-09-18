# 客户话题生成器 Demo

Gradio 网页 + AI 引擎（MiniMax / Claude，均走 Anthropic 兼容协议）。

功能流程：录入客户资料（截图 / 文字）→ AI 提取并建立客户画像 → 生成聊天话题 → 生成候选回复 → 多轮对话陪练。每位客户一份独立存档（`data/customers/<id>.json`）。

## 部署

要求：Python 3.10 以上（在 3.13 上验证）。

```powershell
# Windows：一键脚本（建 .venv、装依赖、生成 .env）
.\setup.ps1            # 按 requirements.txt
.\setup.ps1 -Lock      # 按 requirements.lock.txt 完整锁定版本，跨机器 100% 复现

# Linux / macOS
./setup.sh             # 或 ./setup.sh --lock
```

手动等价步骤：

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

依赖文件说明：`requirements.txt` 只列直接依赖并固定版本；`requirements.lock.txt` 是 `pip freeze` 的完整快照，用于严格复现。

## 启动

```powershell
# 1. 配置 Key
# 编辑 .env，填 MINIMAX_API_KEY 和/或 ANTHROPIC_API_KEY，按需设置代理

# 2. 连通性测试（可选，第二个参数为测试图片）
.venv\Scripts\python scripts\smoke_test.py
.venv\Scripts\python scripts\smoke_test.py some_screenshot.png

# 3. 启动
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
| 我的建模 | 录入**你自己**的聊天截图 / 自述文字，AI 建立你的人格与说话风格画像（口头禅、标点表情习惯、业务姿态、绝不会说的话）。之后回复、话题开场白、对话助手都以你本人口吻生成。全局唯一，存于 `data/me.json` |
| 客户管理 | 列表、新增（姓名 + 标签）、编辑标签、删除（需勾选确认）。点表格某行即切换当前客户 |
| 资料录入 | 上传多张截图 / 粘贴文字，AI 提取客户信息并追加存档；可勾选「提取后立即分析」 |
| 分析页 | 展示客户画像（基本信息 / 性格 / 沟通偏好 / 兴趣 / 痛点 / 关系阶段 / 近期事件 / 禁忌），可重新分析 |
| 话题生成 | 选目的和数量，生成可直接发送的开场白，附理由与注意点；保留历史 |
| 聊天回复 | 粘贴客户消息生成多风格候选回复；下方多轮对话模拟（AI 扮演客户 / AI 做助手），历史按客户保存 |

**支持的上传类型**（客户录入与我的建模相同）：截图 png/jpg/webp/gif；文本 txt/md；表格 xlsx/csv（每个 sheet 转成一条文本材料，前 400 行）；zip 压缩包（自动解开，递归处理其中的图片、文本、表格，忽略其他类型）。旧版 .xls 请先另存为 .xlsx。

**持续加强建模**（对自己、对客户都一样）：
- 材料是追加式的，随时上传新截图 / 新文本；每次更新画像会以**现有画像为基础增量修正**，不会丢掉旧结论。
- 「纠正 / 备注」框可以直接写你确定的事实（例如“王总不喝茶喝咖啡”“我其实很少说哈哈”），不经 AI 提取、建模时权重最高，用来纠偏。
- 任一条材料可按序号删除，删除后建议点一次重新分析。

顶部可切换引擎；「引擎高级设置」可临时覆盖 API Key 和模型名（不写盘），并可勾选是否走 HTTP 代理（地址在 `.env` 的 `PROXY_URL`，`PROXY_ENABLED=true` 则默认勾上）。

## 引擎说明

- **网络**：AI 请求默认忽略系统 `HTTP_PROXY` 环境变量，只按 `.env` 的 `PROXY_URL` / `PROXY_ENABLED` 或页面勾选决定是否走代理。若你的网络只能经代理访问模型接口（本项目当前环境即如此），请保持 `PROXY_ENABLED=true`；直连不通时会在半分钟内报错。

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
