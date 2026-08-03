# 面试准备：技术难点与 Bug 解决实录

> 用途：面试时用来讲"你在这个项目里解决了什么真实的工程问题"
> 每个问题都有：现象 → 根因 → 解决方案 → 面试怎么说

---

## 一、LLM 集成类

### 1. 本地模型不支持 Function Calling → 换模型 + 双模式

**现象:** qwen3-8b-mlx 调用 `with_structured_output(function_calling)` 报错 "Invalid tool_choice type: object"。

**根因:** LM Studio 加载的 qwen3 模型不支持 `tool_choice: "object"` 这个 OpenAI 参数。

**解决过程:**
- 第1次尝试：`method="json_mode"` → qwen3 也不支持
- 第2次尝试：prompt-injection（把 JSON Schema 写进 prompt）→ 嵌套对象解析失败
- 第3次：换模型为 hermes-3-llama-3.1-8b → 支持 `json_schema` 方法 ✅
- 同时设计了 local/cloud 双模式切换（local=json_schema, cloud=function_calling）

**面试说法:** "LangChain 的 structured output 在不同模型上兼容性不一样。我遇到的情况是本地模型不支持 function calling，我做了三层适配：换模型、改 json_schema、双模式自动切换。生产用 DeepSeek 的 function calling，本地用 hermes-3 的 json_schema，一键切换。"

### 2. DeepSeek thinking 模式阻断 function_calling

**现象:** DeepSeek API 返回 "Thinking mode does not support this tool_choice"。

**根因:** DeepSeek v4 默认开启 thinking（推理模式），thinking 和 function calling 互斥。

**解决:** 通过 OpenAI SDK 的 `extra_body` 传 `{"thinking": {"type": "disabled"}}` 关闭 thinking。又遇到 LangChain 传递参数的位置不对（model_kwargs vs 直接传），调试后确定用 ChatOpenAI 的 `extra_body` 参数直接传。

**面试说法:** "DeepSeek 的 thinking 模式很有意思，但和我们需要的 function calling 不兼容。我研究了 DeepSeek 的 API 文档，发现需要用 extra_body 传参数。而且 LangChain 的参数传递有坑——model_kwargs 和直接传参行为不一样，最终确认用 extra_body 直接传给 ChatOpenAI。"

### 3. asyncio.gather 没有真正并行

**现象:** 5 个候选人串行匹配 60s，改成 `asyncio.gather` 后还是 60s。

**根因:** LangChain 的 `ChatOpenAI.async_invoke()` 底层是同步 HTTP 客户端，多个 async 调用在同一个事件循环里排队执行。

**解决:** 改用 `concurrent.futures.ThreadPoolExecutor`，每个候选人在独立线程里用独立的 event loop 执行 LLM 调用。5 人匹配从 60s 降到 ~15s。

**面试说法:** "Python 的 asyncio 不是真正的多线程。LangChain 的异步方法底层是同步 HTTP，所以 asyncio.gather 不会加速。我改用线程池，每个线程独立的事件循环 + HTTP 连接，实现了真正的并行。这是一个典型的 Python 并发陷阱。"

---

## 二、数据流与状态管理类

### 4. 前端列表 API 字段不匹配 → 解析后状态不更新

**现象:** 解析 JD/简历后，Dashboard 显示"已解析: 0"，匹配下拉框为空。

**根因:** `GET /jobs/` 返回 `has_profile: true`（布尔），但前端检查 `j.jd_profile`（对象）。列表 API 不返完整对象所以永远是 `undefined`。

**解决:** 前端改为 `j.has_profile || j.jd_profile` 双检查，兼容两种响应。

**面试说法:** "前后端字段契约不一致是常见问题。我的列表 API 为了性能只返回布尔值 has_profile，但前端用 jd_profile 对象来判断。修复时做了双检查兼容，这是 API 设计中的经典取舍。"

### 5. 解析后名字被 LLM 覆盖

**现象:** 匿名上传的简历（自动命名"申请人A"），解析后名字变成 LLM 从简历里提取的英文名。

**根因:** `crud.update_candidate_profile()` 无条件覆盖 `candidate.name`。

**解决:** 加判断——原名以"申请人"开头（系统自动生成），LLM 提取到真实中文名才更新，英文名或空名保留自动命名。

**面试说法:** "这是隐私保护和功能需求的平衡。匿名简历不暴露姓名，但 LLM 可能从邮箱前缀猜名字。我加了一个保护逻辑：自动命名的候选人，只有 LLM 提取到真实中文名时才更新。这不是简单的 if-else，要考虑假阳性（英文名）和假阴性（真名没提取到）。"

### 6. 匹配结果显示 candidate_id 乱码

**现象:** 排名表显示 `21D4912D`、`ED5B85BD` 这种 UUID，看不出是谁。

**根因:** 排名 API 只返回 `candidate_id`，没有 `name`。

**解决:** 前端同时拉 candidates 列表，构建 `{id → name}` 映射表，排名展示用映射后的名字。

**面试说法:** "这是一个 API 设计问题。排名结果应该有候选人姓名，但我的排名 API 只返回 ID。我不想改 API（避免联调复杂度），就在前端做了 ID→名字的映射查找，类似数据库的 JOIN 但放到了客户端。"

---

## 三、前端交互类

### 7. 快速双击解析按钮导致页面崩溃

**现象:** 快速点"解析"按钮两次，触发重复 API 调用，页面显示加载中卡死。

**根因:** React 的 `useState` 是异步批处理的。两次点击之间 state 还没更新 `parsing[id]=true`，导致两个 API 调用同时发出。

**解决:** 用 `useRef` 做同步锁。`useRef.current` 是同步读写的，不受 React 渲染影响。加锁→执行→解锁。

```typescript
const parsingLock = useRef<Set<string>>(new Set());
if (parsingLock.current.has(id)) return;  // 同步检查
parsingLock.current.add(id);               // 同步加锁
```

**面试说法:** "React 的状态更新是批处理异步的。防抖不能用 useState，因为两次点击之间 state 还没变。我用 useRef 做同步锁，因为 ref 的 .current 是同步读写的，不受 React 渲染周期影响。这个技巧在需要即时响应的场景下很实用。"

### 8. Dashboard 页面切换后数据不刷新

**现象:** 在岗位页解析 JD 后切回首页，"已解析岗位"数字没变。

**根因:** Next.js Pages Router 在页面间切换时复用组件实例，`useEffect([], [])` 不会重新执行。

**解决:** 监听 `router.events.on("routeChangeComplete")`，切回首页时自动重新拉数据。

**面试说法:** "Next.js 的客户端路由不会卸载组件，所以 useEffect 的 cleanup 和重新执行都不会触发。我用了 router.events 监听路由变化，在特定页面激活时手动刷新。这是 SPA 框架里常见的状态同步问题。"

---

## 四、LLM 输出质量类

### 9. JSON 解析失败 → 前端显示原始 JSON

**现象:** 面试评价和邮件在前端显示 `{"technical_depth_score": 8, ...}` 带括号的 JSON 原文。

**根因:** LLM 返回的 JSON 不规范——key 没引号、value 没引号、尾逗号、Python 风格 None/True/False、结构错误（risk_resolution 是对象不是数组）。

**解决过程（6 次迭代）:**
1. 策略 1-4: 直接解析、去 markdown、提取 `{...}`、提取 `[...]`
2. 策略 5: 修复未加引号的 key/value
3. 策略 6: 修复 Python 风格（尾逗号、单引号、None→null）
4. 预处理: Unicode 转义修复（`你` → `你`）
5. Fallback: 解析全失败时清洗 JSON 语法，保留可读文本

**面试说法:** "LLM 的 JSON 输出质量是实际落地最大的坑。我经历了 6 次迭代才稳定：从简单的 json.loads 到 6 层解析策略 + Unicode 修复 + 回退清洗。每次在日志里看到新的 JSON 畸形模式就补一层。这不是一次性解决的，是持续迭代出来的。最后的方案是：先修后解析，解析不了就清洗成可读文本，不让用户看到原始 JSON。"

### 10. Agent 输出英文

**现象:** strengths/concerns/summary 全是英文，中文 JD 配中文简历，输出却是英文。

**根因:** hermes-3 和 DeepSeek 都是英文训练为主，prompt 里说"输出中文"不够强。

**解决:**
- Prompt 改造：用醒目的分隔线块 `═══════ 【语言强制要求】 ═══════` 强调
- 正误示例："技术基础扎实" ✅ / "Strong technical skills" ❌
- Match Agent 加后处理：检测 ASCII > 50% 的字段，自动触发批量翻译

**面试说法:** "让 LLM 稳定输出中文比你想象的要难。光说'输出中文'不够，我在 prompt 里加了视觉强化、正误示例，甚至在 match agent 加了后处理检测——发现英文就自动翻译。这是 prompt engineering 和工程防护的结合。"

---

## 五、基础设施类

### 11. Pydantic Settings 读不到 .env

**现象:** `.env` 里设了 `LLM_MODE=cloud`，但运行后读出来还是 `local`。

**根因:** Pydantic Settings 的嵌套模型 + `env_prefix` 在 v2 里 `.env` 文件加载不稳定。

**解决:** 在 config.py 顶部加 `from dotenv import load_dotenv; load_dotenv()` 手动加载。

**面试说法:** "Pydantic Settings v2 的嵌套模型在加载 .env 文件时 prefix 匹配不太稳定。我先用 python-dotenv 手动把 .env 加载到 os.environ，再让 Pydantic 读取。这是一个库版本兼容性问题。"

### 12. 删除候选人失败 → FK 约束

**现象:** 点删除候选人返回 500 错误 "violates foreign key constraint"。

**根因:** 新增的 `interview_questions`、`interview_evaluations`、`email_drafts` 表引用了 `candidate_id`，但 FK 没配 `ondelete=CASCADE`，Candidate model 也没配 relationship+cascade。

**解决:** 在 `delete_candidate()` 里手动先清理三张子表，再删主记录。同时 model 层也补了 `ondelete="CASCADE"`（但需要重建表才生效）。

**面试说法:** "这是典型的 ORM 级联删除问题。新增了三张表后忘记配 cascade，导致删除候选人时报 FK 约束错误。我在 ORM 层补了 ondelete=CASCADE，同时在业务层也加了手动清理——双重保险。"

---

## 六、RAG 相关

### 13. RAG 证据始终为空

**现象:** 匹配评分全是基于结构化画像，没有简历原文证据。

**根因:** 简历解析流程没有调用 RAG 索引（`index_resume_text()`），Qdrant 里没有 chunks。

**解决:** 在 `POST /resumes/{id}/parse` 端点里，解析成功后自动调 `index_resume_text()` 切分→Embedding→Qdrant，同时 `save_resume_chunks()` → DB。

**面试说法:** "RAG 不只是写一个检索函数。真正的挑战是把索引嵌入到业务流程里。我在简历解析成功后自动触发索引，让后面匹配时能从 Qdrant 检索到证据。这涉及三个服务的协调：document_loader → embedding_service → vector_store。"

### 14. Qdrant point_id 与 DB 记录不一致

**现象:** `store_chunks()` 内部自己生成 UUID，`rag_service.index_resume()` 也生成一套，两套 ID 对不上。

**解决:** `store_chunks()` 接受可选的 `point_ids` 参数，传入时使用外部 ID，并返回实际写入的 ID。

**面试说法:** "这是一个程序间 ID 一致性问题。两个函数各自生成 UUID，存在 Qdrant 里的 ID 和数据库里记录的 ID 对不上，后续检索就找不到。改成了可传外部 ID 的接口，确保两边的 ID 是同一批。"

---

## 七、产品化稳定性与真实联调问题

### 15. 简历解析没有乱码但语义错位

**现象:** 用户粘贴一份中文简历并手动填写候选人姓名，点击解析后，结构化画像里出现 `name: 求职方向`、技能列表里混入 `{}`, `],`, 电话号码片段，教育经历只剩一条且字段错位。

**根因:** 这不是单纯的 Unicode 乱码，而是本地 LLM 的 structured output 在长中文简历上发生了语义错位：章节标题被当成人名，列表边界被模型打散。同时数据库保存逻辑也有一个产品语义 bug：用户手动填写的候选人显示名会被解析结果覆盖。

**解决:**
- 在 Resume Agent 后处理层增加原文规则解析，不完全依赖 LLM。
- 姓名、邮箱、电话优先从简历原文确定性抽取。
- 教育经历、项目经历、实习经历、技能按中文简历常见段落标题解析。
- LLM 输出只作为补充，明显的 JSON 残片、乱码、联系方式碎片会被过滤。
- 修改 `crud.update_candidate_profile()`：手动填写的候选人名称不再被解析结果覆盖；只有系统自动命名的“申请人X”才允许用解析出的真实姓名更新。

**面试说法:** "我一开始以为这是编码问题，但后来发现不是乱码，而是 LLM 把简历结构理解错了。我的修复思路是把确定性信息从 LLM 手里拿回来：联系方式、教育、项目、技能这些有明确格式的字段用规则解析，LLM 负责补充和总结。这样系统既能利用 LLM，又不会把章节标题当成人名。这是 LLM 产品里很重要的原则：不要把所有字段都交给生成模型。"

### 16. 多人解析完成后页面突然白屏加载

**现象:** 在简历页面快速点击多个候选人的“解析”，第一个解析完成后页面突然变白并显示“加载中”，导致其他候选人的按钮无法继续操作。

**根因:** 前端 `loadCandidates()` 每次刷新列表都会设置全局 `loading=true`。页面只要看到 `loading=true` 就直接返回整页 loading 组件，所以单个解析完成后的列表刷新会卸载整个页面。多个解析并发时，第一个完成的请求会打断其他操作。

**解决:**
- 首次进入页面保留整页 loading。
- 解析、上传、删除后的列表刷新改成后台同步状态 `refreshing`。
- 单个候选人解析成功后，先在本地列表里就地更新该卡片为“已解析”，再后台刷新完整列表。
- 每个候选人仍然保留独立 `parsing[id]` 和 `useRef` 防抖锁。

**面试说法:** "这个问题不是接口慢，而是前端状态粒度太粗。以前一个候选人解析完成会触发全局 loading，整个页面被卸载。我把 loading 拆成首次加载和后台刷新两种状态，并且解析成功后先局部更新对应卡片。这样用户可以连续操作多个候选人，页面不会被单个请求打断。"

### 17. 弹窗被顶部导航遮挡且无法滚动

**现象:** 在简历列表往下滚动后点击“详情”，弹窗出现在页面上方，被顶部导航遮住，甚至关闭按钮也被挡住；第一次修复时又出现弹窗打开后页面上下无法滚动的问题。

**根因:** 弹窗定位和滚动策略没有区分页面滚动与弹层滚动。原实现的 z-index 不够高，且曾经用 `body.style.overflow = hidden` 锁住页面，导致长内容详情无法自然滚动。

**解决:**
- 统一岗位、简历、匹配详情弹窗的层级为高 z-index。
- 弹层容器使用 `fixed inset-0 overflow-y-auto`，滚动交给遮罩层自身。
- 移除全局 body 滚动锁，避免详情内容较长时无法查看。
- 详情卡片使用 sticky header，让关闭按钮始终可见。

**面试说法:** "这个问题体现的是前端工程里的细节：modal 不只是居中，还要考虑滚动位置、导航层级和长内容。我的最后方案是让遮罩层自己滚动，而不是锁 body；同时提高 z-index 并让弹窗头部 sticky。这样用户从任何滚动位置打开详情，都能看到完整弹窗。"

### 18. Top 5 匹配接口返回 Failed to fetch

**现象:** 在匹配与面试页面选择 Top 5 后，前端报 `Failed to fetch`，看起来像后端没启动。

**根因:** Uvicorn 实际是启动的。后端日志显示 `/jobs/{id}/match?limit=5` 返回 500，根因是 Match Agent 调本地 LLM 时输出超过 `max_tokens=2047`，OpenAI/LangChain 在结构化解析阶段抛出 `LengthFinishReasonError`。前端只看到网络请求失败，所以提示不够准确。

**解决:**
- 缩短 Match Agent 输入：技能、项目描述、工作经历、RAG 证据都限制数量和长度。
- Prompt 明确要求输出简洁：优势、风险、证据最多 3 条，summary 不超过 60 字。
- 给 `match_candidate()` 加规则兜底：单个候选人 LLM 精排失败时，按技能重合度、项目、教育、经验生成可解释的兜底评分。
- 批量匹配不再因为一个候选人 LLM 输出截断而整体 500。

**面试说法:** "这个问题表面上是前端 Failed to fetch，但真正原因在后端 LLM 结构化输出被截断。我做了两层防护：第一减少输入和限制输出，降低触发概率；第二给单个候选人加兜底评分，保证 Top 5 匹配接口不会因为一个 LLM 调用失败而整体失败。我的思路是，LLM 可以失败，但业务流程不能因为一次生成失败就崩掉。"

### 19. Top 5 匹配从 40 多秒明显加速

**现象:** 即使用了多线程并发调用本地模型，Top 5 匹配仍然很慢，经常要 40 多秒。表面上看已经是多个候选人并行评分，但整体等待时间还是很长。

**根因:** 并发只能解决“多个请求串行排队”的问题，不能解决“单个 LLM 请求本身太重”的问题。之前 Match Agent 给本地模型的输入太大：完整项目描述、完整技能列表、较长 JD 字段、多个 RAG 证据片段都会塞进 prompt；同时输出也没有严格限制，模型会生成很长的 strengths、risks、summary 和 evidence。结果就是每个候选人的单次推理时间很长，即使 5 个并发，总耗时仍然被最慢的那个长请求拖住。

**解决:**
- 对 Match Agent 输入做裁剪：JD 技能/职责限制条数，候选人技能限制数量，项目描述截断，RAG 证据只取前 3 条且每条截断。
- 对输出做强约束：strengths 最多 3 条，risks 最多 3 条，evidence 最多 3 条，summary 不超过 60 字。
- 保留 ThreadPool 并发，让 Top 5 仍然并行跑，但每个并发任务都变轻。
- 增加 prompt 长度测试，避免后续改动又把 prompt 悄悄变长。

**面试说法:** "我最开始以为性能瓶颈主要是并发，所以用了 ThreadPool 并行跑多个候选人。但后来发现即使并发，Top 5 还是要 40 多秒，因为每个 LLM 请求本身太重。我做的优化是把 prompt 变短、把输出变短：候选人项目、技能和 RAG 证据都只保留最有用的信息，同时限制模型不要长篇解释。这个优化的思路是，LLM 性能不只看并发数，还要控制每次调用的 token 成本。最后效果是 Top 5 查询明显变快，而且输出更稳定。"

---

## Bug 分类统计

| 类别 | 数量 | 典型问题 |
|---|---|---|
| LLM 集成 | 3 | function calling 兼容、thinking 冲突、假并行 |
| 数据流 | 4 | 字段错配、名字覆盖、ID 显示、简历语义错位 |
| 前端交互 | 4 | 双击崩溃、数据不刷新、全页 loading、弹窗滚动层级 |
| LLM 输出质量 | 3 | JSON 解析、中文输出、匹配输出截断 |
| 性能调优 | 1 | 控制 prompt/token 成本 |
| 基础设施 | 2 | 读不到 .env、FK 约束 |
| RAG | 3 | 索引缺失、ID 不一致、空检索掩盖索引故障 |
| Agent 架构与容错 | 3 | Workflow/ReAct 组合、关键词安全误判、本地 Tool Call 参数兼容 |
| **总计** | **23** |  |

---

## 八、Agent 架构与 Tool Calling 容错

### 20. 项目本质是 Workflow，如何加入真正的 ReAct 和 Tool Calling

**背景:** HireFlow 原本虽然叫“多 Agent 系统”，但 Agent 都是固定节点里的单次
LLM 调用。面试官如果追问 ReAct、Tool Calling、Observation 和错误恢复，原架构
缺少一个可以实际演示的动态循环。

**设计取舍:** 没有把整个招聘流程改成自由行动的 Supervisor Agent。招聘属于
高风险场景，JD 解析、评分、排序和人工审核仍走确定性 LangGraph Workflow；只在
不确定性最高、风险较低且完全只读的“简历证据检索”环节嵌入受控 ReAct 子图。

```text
reason --> search_resume_evidence Tool Call --> Qdrant Observation
   ^                                                  |
   |                                                  |
   |------------ 改写查询，最多3轮 -------------------|
                              |
                              --> EvidencePack --> Match Agent
```

**具体实现:**

- 使用 `ChatOpenAI.bind_tools()` 把搜索工具和覆盖率工具的 JSON Schema 交给模型。
- 使用 LangGraph `StateGraph` 构建 `reason → tools → reason` 反馈循环。
- `candidate_id` 不信任模型输出，由运行时从当前 LangGraph 状态注入；模型只负责评分维度、查询词和 `top_k`。
- 自定义受控 tools 节点，而不是直接放开通用工具执行器；节点统一完成候选人隔离、参数校验、错误分类、指数退避和审计。
- Agent 最多 3 轮、6 次 Tool Call；同一组参数禁止重复调用。
- 不保存隐藏 CoT，只保存工具名、参数、Observation、尝试次数、耗时和停止原因。
- 工具重试耗尽后，API 和前端给出“重试、带警告继续、跳过、终止”四种选择；正式 LangGraph 流程使用 `interrupt()` + PostgresSaver 暂停恢复。

**错误策略:**

| 错误 | 是否原参数重试 | 最终处理 |
|---|---:|---|
| Timeout / ConnectionError / 429 / 5xx | 是，总尝试3次 | 耗尽后人工选择 |
| query 为空、非法维度、重复参数 | 否 | ToolMessage 返回 Agent 改参数，最多修正2次 |
| 工具正常但返回空列表 | 否 | 这是证据不足，不是系统异常 |
| 跨候选人访问、受保护属性 | 否 | 立即阻断并记录安全错误 |
| 模型调用失败 | 仅临时错误重试 | 耗尽后人工选择 |

**面试说法:** “我的框架是 LangGraph/LangChain，整体架构是 deterministic
workflow，但证据检索节点是 bounded ReAct Agent。模型通过原生 Tool Calling
动态查询 Qdrant，再读取 ToolMessage Observation 决定是否改写查询。为了满足
招聘场景的可控性，我设置三轮和六次工具预算，并把基础设施重试与 Agent 重新
规划分开：网络错误指数退避，参数错误让模型改写，安全错误不重试，重试耗尽就
通过 interrupt 交给人。最终招聘决定始终由人工完成。”

### 21. 安全关键词子串误判：`age` 把 `Agent` 当成年龄查询

**现象:** 第一版受保护属性过滤上线测试后，正常查询
`Python LangGraph Agent 开发` 被立即拦截，错误信息是“查询包含受保护属性”。

**根因:** 英文年龄关键词使用了简单的子串判断：`"age" in query.lower()`。
`Agent` 转成小写后是 `agent`，其中恰好包含连续子串 `age`，因此被误判为查询年龄。
同类问题还可能出现在 `race` 等英文词上。

**解决:** 中文敏感词继续使用包含判断；英文敏感词改成正则单词边界匹配：

```python
re.search(r"\bage\b", query.lower())
```

同时保留跨候选人 ID 校验，让安全检查发生在访问 Qdrant 之前，并增加回归测试
验证正常的 `Agent` 查询可通过、真正的 `age` 查询仍会阻断。

**面试说法:** “这是典型的安全规则假阳性。简单黑名单会把 age 匹配到 Agent，
不仅影响召回，还会让正常候选人被错误标记。我把中文包含匹配和英文词边界匹配
分开，并用测试锁住这个边界。安全规则不能只追求拦截率，也要控制误伤率。”

### 22. 本地模型省略 `candidate_id` 被误判为跨候选人访问

**现象:** 真实 LM Studio 联调时，前端 Agent 轨迹同时出现两类红色错误：一部分
Tool Call 没有填写 `candidate_id`，被报成 `TOOL_SECURITY_BLOCKED`；另一部分使用
`search_evidence`、`query_text`、`technical` 等语义正确但不完全符合 schema 的名称，
连续修正后触发 `TOOL_ARGUMENT_REPAIR_EXHAUSTED`。

**根因:** 第一版把 `candidate_id` 当作模型必须生成的工具参数，并用“不等于当前
候选人”统一判断越权。因此空字符串也被当成恶意跨候选人请求。OpenAI 兼容协议
只保证 Tool Call 的基本结构，不同本地模型对工具名和参数枚举的服从度并不一致，
所以过严的执行器会把可以无损修复的格式差异升级成业务中断。

**解决:** 把身份参数和业务参数分开处理：

- `candidate_id` 由受控 tools 节点从当前 `HiringState` 注入，模型省略它是正常情况。
- 只有模型主动填写了另一个非空 ID 时，才判定为真正的跨候选人访问并立即阻断。
- 对语义等价的工具名、维度名、`query_text/search_query` 和数字字符串做白名单规范化。
- 缺少 query 时根据当前 JD 和维度生成确定性检索词；无法安全兼容的参数仍返回
  `ToolMessage`，并附一份合法调用示例供模型修正。
- 审计轨迹保存系统最终执行的规范参数，便于解释数据到底是如何被访问的。

**面试说法:** “Tool Calling 不能只做 schema 校验，还要区分可信运行时上下文和
模型生成参数。候选人 ID 属于授权边界，所以我不让模型决定，而是从图状态注入；
空 ID 可以补全，非空且不同的 ID 才阻断。对本地模型常见的字段别名我做白名单
规范化，但不会放宽安全边界。这既降低误报，也避免模型越权访问其他候选人。”

### 23. 所有候选人都显示 `search_completed_without_evidence`

**现象:** Agent 没有抛异常，所有 Tool Call 都显示“未找到证据”，最终每位候选人
都是 `search_completed_without_evidence`。看起来像所有简历都没有相关项目，实际
上 Qdrant 中根本没有这些候选人的向量块。

**根因:** 简历解析由两个相互独立的步骤组成：Resume Agent 生成画像，以及
Embedding + Qdrant 建立 RAG 索引。旧代码为了不阻塞画像解析，用空 `except/pass`
吞掉了索引异常。因此用户看到“已解析”，但 Embedding 模型未加载或 Qdrant 不可用
时，索引实际上没有建立。Qdrant 带 `candidate_id` 过滤的搜索返回空列表后，Agent
又把它当成正常业务空结果，最终把基础设施故障错误归因成候选人缺少证据。

**解决:** 建立三层防线：

- 简历解析响应增加 `rag_indexed` 和 `rag_index_warning`，索引失败不再静默。
- 匹配前按 `candidate_id` 统计 Qdrant 点数；缺失时使用 PostgreSQL 保存的简历原文
  自动重新切块、生成 Embedding 并写回 Qdrant。
- Tool 搜索返回空列表后再次确认候选人索引是否存在；索引缺失抛
  `ResumeIndexMissingError`，作为基础设施错误交给人工，而不再标记业务证据不足。
- 实际联调继续发现新版 `langchain-qdrant` 不允许 dense 模式使用
  `embedding=None`。项目已经自行生成向量，因此移除无用的 `QdrantVectorStore`
  包装，集合初始化直接返回 QdrantClient，再用底层 `upsert` 写入向量和 Payload。

**面试说法:** “空结果不一定是业务事实，也可能是上游数据管道没有成功执行。
Qdrant 没设置相似度阈值时，只要 candidate_id 下存在向量，Top K 就至少返回一条；
所以零结果可以作为索引缺失的强信号。我增加了匹配前健康检查和自动重建，并把
索引缺失与真实低相关证据分开建模，避免系统故障影响候选人判断。”

## ReAct Agent 高频追问速答

**Q：你用的是 React、ReAct 还是 ToT？**

A：前端使用 React；Agent 框架使用 LangGraph/LangChain；整体是确定性 Workflow，
证据检索阶段使用 bounded ReAct。项目没有使用 ToT，因为当前任务不需要维护和
剪枝多条推理树，成本和不可控性都更高。

**Q：为什么不用官方 ToolNode？**

A：ToolNode 适合通用工具执行，但招聘证据检索需要候选人数据隔离、受保护属性
校验、错误分类、指数退避和详细审计。因此我保留原生 Tool Calling 协议，自定义
受控 tools 节点；模型仍然生成标准 tool_calls，节点返回标准 ToolMessage。

**Q：为什么不对所有错误都重试？**

A：网络抖动和 5xx 可能自行恢复，适合原参数重试；参数错误重复调用没有意义，
应该让 Agent 改参数；安全错误重试反而可能扩大风险，必须立即阻断；正常空结果
是业务事实，也不应该伪装成系统异常。
