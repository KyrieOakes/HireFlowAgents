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

## Bug 分类统计

| 类别 | 数量 | 典型问题 |
|---|---|---|
| LLM 集成 | 3 | function calling 兼容、thinking 冲突、假并行 |
| 数据流 | 3 | 字段错配、名字覆盖、ID 显示 |
| 前端交互 | 2 | 双击崩溃、数据不刷新 |
| LLM 输出质量 | 2 | JSON 解析、中文输出 |
| 基础设施 | 2 | 读不到 .env、FK 约束 |
| RAG | 2 | 索引缺失、ID 不一致 |
| **总计** | **14** | |
