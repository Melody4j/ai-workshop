# llm-service

## Module

- 服务入口：[backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- Client 封装：[backend/apps/intelligence/services/llm_client.py](../../../backend/apps/intelligence/services/llm_client.py)
- 重试机制：[backend/apps/intelligence/services/retry.py](../../../backend/apps/intelligence/services/retry.py)
- Prompt 模板：[backend/prompts/](../../../backend/prompts/)
- Prompt 优化服务：[backend/apps/intelligence/services/prompt_optimizer_service.py](../../../backend/apps/intelligence/services/prompt_optimizer_service.py)
- 配置入口：[backend/config/settings.py](../../../backend/config/settings.py)（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS）

## Service Contract

### 3 次独立 LLM 调用（情报生成链路）

1. **denoise(bs_clean_md) → str**：LLM 语义降噪，输入 BS 清洗后 MD，输出降噪后 MD（Prompt: `prompts/denoise.md`）
2. **judge_diff(diff_text, self_product_doc) → dict**：LLM diff 判断，返回 `{"has_meaningful_change": bool, "reason": str}`（Prompt: `prompts/judge_diff.md`）
3. **generate_intel(diff_text, self_product_doc, few_shots) → IntelResult**：LLM 情报生成，instructor + Pydantic 结构化输出 4 字段（Prompt: `prompts/intel_system.md` + `prompts/intel_user.md`）

### 第 4 次 LLM 调用（Prompt 优化，Spec 006 新增）

4. **optimize_prompts(feed_id) → dict**：收集 diff_text + clean_md + AI 报告 4 字段 + 用户评语 + 当前 prompt 全文 → 注入 `prompts/prompt_optimizer.md` → instructor + Pydantic `OptimizedPrompts` schema → 一次返回优化后的 intel_system + intel_user 全文 → PromptVersion 存档 → `save_prompt` 覆盖文件

### OptimizedPrompts（Pydantic 模型，Spec 006 新增）

- `intel_system`：优化后的 system prompt 全文
- `intel_user`：优化后的 user prompt 全文

### Prompt Loader（Spec 006 新增 save_prompt）

- `load_prompt(name, **kwargs)`：读取 `prompts/{name}.md`，str.replace 注入变量
- `save_prompt(name, content)`：将内容覆盖写回 `prompts/{name}.md`（UTF-8），仅 `prompt_optimizer_service` 调用

### IntelResult（Pydantic 模型）

- `change_summary`：变化摘要
- `strategic_intent`：战略意图
- `action_suggestion`：行动建议
- `evidence_diff`：证据 diff

### Negative Few-Shot

- `get_negative_few_shots(project_id) → list`：查询最近 5 条 `user_feedback=-1` 的 IntelligenceFeed

### Invariants

1. 3 次 LLM 调用独立，不合并（denoise / judge_diff / generate_intel）
2. 第 4 次 LLM 调用（optimize_prompts）独立于情报生成 3 次调用链路，仅由评分=-1 触发（Spec 006 新增）
3. `generate_intel` 使用 instructor + Pydantic（IntelResult 4 字段结构化输出）
4. 每次 LLM 调用独立重试（3 次 / 30s 间隔），不降级
5. LLM 密钥从 `.env` 读取（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），不硬编码不入库
6. Negative Few-Shot 注入上限最近 5 条（`user_feedback=-1`）
7. OpenAI 兼容 API（覆盖 OpenAI / DeepSeek / 通义 / Moonshot）
8. 情报输出固定 4 字段，不含价值度字段
9. `optimize_prompts` 一次 LLM 调用返回 intel_system + intel_user 两个 prompt，不分两次（Spec 006 新增）
10. `optimize_prompts` 返回内容校验：< 50 字符 → raise ValueError（Spec 006 新增）
11. `save_prompt` 直接覆盖文件，无审批步骤；退化风险由 PromptVersion 回滚兜底（Spec 006 新增）

### Evidence

- [backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- [backend/apps/intelligence/services/llm_client.py](../../../backend/apps/intelligence/services/llm_client.py)
- [backend/apps/intelligence/services/retry.py](../../../backend/apps/intelligence/services/retry.py)
- [backend/apps/intelligence/services/prompt_loader.py](../../../backend/apps/intelligence/services/prompt_loader.py)
- [backend/apps/intelligence/services/prompt_optimizer_service.py](../../../backend/apps/intelligence/services/prompt_optimizer_service.py)
- [backend/prompts/](../../../backend/prompts/)
- [backend/apps/intelligence/tests/test_llm_service.py](../../../backend/apps/intelligence/tests/test_llm_service.py)
- [backend/apps/intelligence/tests/test_llm_client.py](../../../backend/apps/intelligence/tests/test_llm_client.py)
- [backend/apps/intelligence/tests/test_prompt_loading.py](../../../backend/apps/intelligence/tests/test_prompt_loading.py)
- [backend/apps/intelligence/tests/test_retry.py](../../../backend/apps/intelligence/tests/test_retry.py)
- [backend/apps/intelligence/tests/test_prompt_optimizer_service.py](../../../backend/apps/intelligence/tests/test_prompt_optimizer_service.py)

## Evidence Gaps

- 缺口：LLM 延迟/成本基线尚无实测数据（V 阶段未执行）
  - 影响：无法声明 LLM 调用延迟 NFR 达标
  - 建议动作：V 阶段实测 3 次调用总计延迟与 token 成本
