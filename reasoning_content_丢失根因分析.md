# 根因分析：DeepSeek thinking mode reasoning_content 丢失问题

> GitHub Issue #11
> 分析人：小程（开源分析组）
> 日期：2026-05-27

---

## 一、问题描述

DeepSeek thinking mode（深度思考模式）的 API 要求客户端在后续请求中回传 `reasoning_content` 字段，以保持思考链的连续性。但在 TogoSpace 的 compact（上下文压缩）机制执行后，历史 assistant 消息中的 `reasoning_content` 会丢失，导致 DeepSeek 等 CoT 模型的思考链断裂。

---

## 二、根因分析

### 2.1 reasoning_content 的存储与序列化链路

`OpenAIMessage` 模型定义（`OpenAiModels.py:14`）：

```python
class OpenAIMessage(BaseModel):
    role: OpenaiApiRole
    content: Optional[str] = None
    reasoning_content: Optional[str] = Field(None, description="推理内容（如 CoT 模型），仅响应侧使用")
    tool_calls: Optional[List[OpenAIToolCall]] = None
    tool_call_id: Optional[str] = None
```

关键点：
- **存储链路完整**：`OpenAIMessage` 的 `to_dict()` 使用 `model_dump(mode="json", exclude_none=True)`，会将非 None 的 `reasoning_content` 序列化到 JSON。数据库通过 `PydanticJsonField(OpenAIMessage)` 存储，写入时 `reasoning_content` 被保留。
- **推理侧保存完整**：`agentTurnRunner.py:562-565` 在推理成功后将 `reasoning_content` 作为 `AgentActivityType.REASONING` 活动记录保存。同时，`assistant_message` 整体通过 `finalize_history_item()` 写入 `GtAgentHistory`，`reasoning_content` 随 `OpenAIMessage` 一起持久化。

**结论：reasoning_content 在存储层没有丢失。**

### 2.2 compact 执行后原始消息如何丢失

compact 的执行流程（`agentTurnRunner.py:814-848`）：

1. `build_compact_plan()` 计算压缩范围 → `source_messages`（待压缩的旧消息列表）
2. `compact_messages()` 调用 LLM 生成摘要 → 返回 `summary_text`
3. `insert_compact_summary()` 将摘要作为一条 `USER` 角色消息插入，标签为 `COMPACT_SUMMARY`
4. **旧的前缀消息（包含原始 assistant 消息及其 reasoning_content）从内存中移除**

关键代码（`agentHistoryStore.py:495-555`）：

```python
async def insert_compact_summary(self, message, seq):
    # 找出 seq >= insert_seq 的保留尾部
    preserved_items = self._items[preserve_idx:]
    # compact summary 插入，原前缀被丢弃
    self._items = [item] + preserved_items
```

**数据库层面**：`get_agent_history_after_compact()` 只查询 `seq >= compact_seq` 的记录，旧前缀（包含原始 assistant 消息）**不再被加载**。

### 2.3 build_infer_messages() 在 compact 后如何构造消息

```python
def build_infer_messages(self) -> list[OpenAIMessage]:
    items = list(self._items)
    if self.get_pending_infer_item() is not None:
        items = items[:-1]
    return [item.openai_message for item in items if item.has_message]
```

compact 后，`self._items` 的结构变为：

```
[COMPACT_SUMMARY (USER角色，摘要文本), 保留的尾部消息...]
```

`build_infer_messages()` 返回的所有 `OpenAIMessage` 中，COMPACT_SUMMARY 是一条普通 USER 消息（**不含 reasoning_content**），后续保留的尾部消息可能包含 assistant 消息，但这些 assistant 消息是最新的——如果它们产生在 compact 之前的对话中，它们的 `reasoning_content` 已经随旧前缀一起被裁掉了。

### 2.4 丢失场景的完整链路

以 DeepSeek 的一个会话为例：

```
[USER: u1, ASSISTANT(reasoning_content=思考1, content=回复1), USER: u2, ASSISTANT(reasoning_content=思考2, content=回复2), ...]
```

1. **compact 前**：所有 `reasoning_content` 都完整存储在数据库中
2. **compact 执行**：
   - 旧前缀 `[USER: u1, ASSISTANT(思考1, 回复1), USER: u2]` 被送入 LLM 生成摘要
   - 摘要文本是一段自然语言描述，**不包含 reasoning_content**
   - 旧前缀从数据库查询范围和内存中移除
   - 新的 `_items` 以 `[USER: COMPACT_SUMMARY(摘要)]` 开头
3. **compact 后下次推理**：
   - `build_infer_messages()` 只能拿到 `[COMPACT_SUMMARY, ASSISTANT(思考2, 回复2), ...]`
   - `ASSISTANT(思考2, 回复2)` 如果在保留区，其 `reasoning_content` 仍在
   - 但 `ASSISTANT(思考1, 回复1)` 已丢失，其 `reasoning_content` 随之丢失
4. **DeepSeek API 要求**：发送消息时需要回传所有 assistant 消息的 `reasoning_content`，但 compact 摘要无法保留这种结构化信息

### 2.5 其他可能导致 reasoning_content 丢失的场景

| 场景 | 是否丢失 | 分析 |
|------|:--------:|------|
| **compact 摘要替代旧前缀** | ✅ 丢失 | 摘要是纯文本，无法包含结构化的 `reasoning_content` |
| **`_trim_to_latest_compact` 恢复裁剪** | ✅ 丢失 | 进程重启时只加载 COMPACT_SUMMARY 之后的数据，旧 assistant 的 `reasoning_content` 不被加载 |
| **`get_agent_history_after_compact` DB 查询** | ✅ 丢失 | 只查 `seq >= compact_seq`，旧记录不被查到 |
| **`build_infer_messages()`** | ✅ 丢失 | 只转换 `self._items` 中的消息，不在 items 中的不会被包含 |
| **正常推理（无 compact）** | ❌ 不丢失 | 完整历史被加载和传递 |

---

## 三、影响范围

### 受影响模型

- **DeepSeek Chat / DeepSeek Reasoner**：明确要求回传 `reasoning_content`，丢失后思考链断裂，模型可能出现：重复思考、胡乱续写、输出质量下降
- **GLM-4 系列**（如果支持 CoT）：同理受影响
- **其他支持思考模式的模型**：任何要求回传 `reasoning_content` 的模型均受影响

### 触发条件

1. 使用 DeepSeek 等 CoT 模型
2. 对话足够长，触发 compact（`estimated_tokens >= trigger_tokens`，默认为 context_window * 0.85）
3. compact 发生后，下次推理时思考链丢失

### 不受影响的场景

- 非 CoT 模型（`reasoning_content` 始终为 None）
- 对话较短未触发 compact
- compact 后保留区中最新 assistant 消息的 `reasoning_content`（仍在 items 中）

---

## 四、修复方案建议

### 方案 A：在 COMPACT_SUMMARY 中保留 reasoning_content（推荐）

**思路**：compact 生成摘要后，将所有被压缩的 assistant 消息中的 `reasoning_content` 拼接到摘要消息中，作为结构化字段保留。

**改动点**：

1. **`compact.py` → `compact_messages()`**：返回值增加 `collected_reasoning`，收集被压缩消息中所有非空 `reasoning_content`

```python
# compact_messages 返回值改为 (summary_text, collected_reasoning) 或增加参数
async def compact_messages(...) -> tuple[str | None, str | None]:
    # ... 现有逻辑 ...
    # 收集被压缩消息中所有 assistant 的 reasoning_content
    collected_reasoning = []
    for msg in messages:
        if msg.role == "assistant" and msg.reasoning_content:
            collected_reasoning.append(msg.reasoning_content)
    reasoning_text = "\n\n".join(collected_reasoning) if collected_reasoning else None
    return promptBuilder.build_compact_resume_prompt(summary), reasoning_text
```

2. **`agentTurnRunner.py` → `_execute_compact()`**：将 `reasoning_text` 附加到 COMPACT_SUMMARY 消息

```python
summary_text, reasoning_text = await compact.compact_messages(...)
summary_message = llmApiUtil.OpenAIMessage.text(
    llmApiUtil.OpenaiApiRole.USER, summary_text
)
summary_message.reasoning_content = reasoning_text  # 保留思考链
await self._history.insert_compact_summary(summary_message, seq=compact_plan.insert_seq)
```

3. **`build_infer_messages()`**：确保 COMPACT_SUMMARY 消息中的 `reasoning_content` 被 `to_dict()` 序列化传出（已支持，因为 `model_dump(exclude_none=True)` 不会排除非 None 的 `reasoning_content`）

**优点**：改动最小，与现有 compact 机制兼容
**缺点**：如果被压缩的 reasoning_content 很多，可能仍然很长；本质上是将结构化的推理内容合并成一段文本，逻辑上仍然有信息损失

### 方案 B：保留被压缩消息的 assistant 消息（带 reasoning_content），仅压缩 USER 消息

**思路**：修改 compact 策略，被压缩的 assistant 消息（含 `reasoning_content`）不参与摘要，而是原样保留在历史中。只有 USER 消息被压缩为摘要。

**改动点**：

1. **`agentHistoryStore.py` → `build_compact_plan()`**：`source_messages` 只包含 USER 角色消息，assistant 消息保留
2. 保留区的计算需要调整

**优点**：完整保留 reasoning_content 的结构化信息
**缺点**：compact 效果减弱（assistant 消息无法压缩）；token 节省比例下降

### 方案 C：数据库层面保留被压缩的 reasoning_content，compact 时重建

**思路**：compact 时不删除旧前缀的数据库记录（或保留一个压缩视图），在 `build_infer_messages()` 时，对 COMPACT_SUMMARY 前的 assistant 消息的 `reasoning_content` 进行重建。

**改动点**：

1. 数据库不物理删除旧记录，只是标记为已压缩
2. `get_agent_history_after_compact()` 改为加载完整历史
3. `build_infer_messages()` 针对被压缩的 assistant 消息，只取 `reasoning_content` 字段，其余内容被 COMPACT_SUMMARY 替代

**优点**：信息无损
**缺点**：改动大，与当前 compact 设计理念冲突（compact 的目的就是减少加载的数据量）

---

## 五、推荐方案

**推荐方案 A**，理由：

1. **改动量最小**：只需修改 `compact_messages()` 和 `_execute_compact()` 两处，约 20-30 行代码
2. **兼容性好**：不改变 compact 的核心逻辑（摘要生成、前缀裁剪），只增加一个字段
3. **DeepSeek API 兼容**：`reasoning_content` 作为 assistant 消息的非标准字段，DeepSeek 在接收时会将其识别为历史思考链
4. **向后兼容**：对于不使用 `reasoning_content` 的模型，该字段为 None，`exclude_none=True` 序列化时自动忽略

### 方案 A 的边界情况

- **多轮 compact**：每次 compact 时需要合并新旧 reasoning_content，避免中间摘要的 reasoning 段丢失
- **reasoning_content 过长**：如果被压缩的 reasoning_content 本身超出 compact_summary_max_tokens，应截断或仅保留最近 N 轮的 reasoning
- **COMPACT_SUMMARY 本身的 reasoning_content**：它的角色是 USER（人为构造），DeepSeek API 是否会接受 USER 角色的 `reasoning_content`？→ 需要验证。如果 DeepSeek 只接受 ASSISTANT 角色的 `reasoning_content`，则方案 A 需要调整：将收集的 reasoning 拼成独立的 ASSISTANT 消息插在 COMPACT_SUMMARY 之前

---

## 六、补充建议

1. **添加集成测试**：覆盖 "compact 后 build_infer_messages 包含 reasoning_content" 的场景
2. **添加单元测试**：覆盖 `compact_messages()` 返回 reasoning_text 的逻辑
3. **日志监控**：在 `_execute_compact()` 中记录被压缩的 reasoning_content token 估算值，便于线上监控 compact 对思考链的影响
4. **配置项**：添加 `preserve_reasoning_in_compact` 配置开关（默认开启），允许用户按模型选择是否在 compact 中保留 reasoning_content