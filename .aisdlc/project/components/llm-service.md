# llm-service

## Module

- 服务入口：[backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- Client 封装：[backend/apps/intelligence/services/llm_client.py](../../../backend/apps/intelligence/services/llm_client.py)
- 重试机制：[backend/apps/intelligence/services/retry.py](../../../backend/apps/intelligence/services/retry.py)
- Prompt 模板：[backend/apps/intelligence/prompts/](../../../backend/apps/intelligence/prompts/)
- 配置入口：[backend/config/settings.py](../../../backend/config/settings.py)（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TEMPERATURE / LLM_MAX_TOKENS）

## Service Contract

### 3 次独立 LLM 调用

1. **denoise(bs_clean_md) → str**：LLM 语义降噪，输入 BS 清洗后 MD，输出降噪后 MD（Prompt: `prompts/denoise.md`）
2. **judge_diff(diff_text, self_product_doc) → dict**：LLM diff 判断，返回 `{"has_meaningful_change": bool, "reason": str}`（Prompt: `prompts/judge_diff.md`）
3. **generate_intel(diff_text, self_product_doc, few_shots) → IntelResult**：LLM 情报生成，instructor + Pydantic 结构化输出 4 字段（Prompt: `prompts/generate_intel.md`）

### IntelResult（Pydantic 模型）

- `change_summary`：变化摘要
- `strategic_intent`：战略意图
- `action_suggestion`：行动建议
- `evidence_diff`：证据 diff

### Negative Few-Shot

- `get_negative_few_shots(project_id) → list`：查询最近 5 条 `user_feedback=-1` 的 IntelligenceFeed

### Invariants

1. 3 次 LLM 调用独立，不合并（denoise / judge_diff / generate_intel）
2. `generate_intel` 使用 instructor + Pydantic（IntelResult 4 字段结构化输出）
3. 每次 LLM 调用独立重试（3 次 / 30s 间隔），不降级
4. LLM 密钥从 `.env` 读取（LLM_API_KEY / LLM_BASE_URL / LLM_MODEL），不硬编码不入库
5. Negative Few-Shot 注入上限最近 5 条（`user_feedback=-1`）
6. OpenAI 兼容 API（覆盖 OpenAI / DeepSeek / 通义 / Moonshot）
7. 情报输出固定 4 字段，不含价值度字段

### Evidence

- [backend/apps/intelligence/services/llm_service.py](../../../backend/apps/intelligence/services/llm_service.py)
- [backend/apps/intelligence/services/llm_client.py](../../../backend/apps/intelligence/services/llm_client.py)
- [backend/apps/intelligence/services/retry.py](../../../backend/apps/intelligence/services/retry.py)
- [backend/apps/intelligence/prompts/](../../../backend/apps/intelligence/prompts/)
- [backend/apps/intelligence/tests/test_llm_service.py](../../../backend/apps/intelligence/tests/test_llm_service.py)
- [backend/apps/intelligence/tests/test_llm_client.py](../../../backend/apps/intelligence/tests/test_llm_client.py)
- [backend/apps/intelligence/tests/test_prompt_loading.py](../../../backend/apps/intelligence/tests/test_prompt_loading.py)
- [backend/apps/intelligence/tests/test_retry.py](../../../backend/apps/intelligence/tests/test_retry.py)

## Evidence Gaps

- 缺口：LLM 延迟/成本基线尚无实测数据（V 阶段未执行）
  - 影响：无法声明 LLM 调用延迟 NFR 达标
  - 建议动作：V 阶段实测 3 次调用总计延迟与 token 成本
