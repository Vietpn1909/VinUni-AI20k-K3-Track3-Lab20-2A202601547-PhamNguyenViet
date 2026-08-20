# Design Template

## Problem

Xây dựng hệ thống research assistant tự động: nhận câu hỏi nghiên cứu từ người dùng, tìm kiếm thông tin từ nhiều nguồn, phân tích và tổng hợp thành câu trả lời có trích dẫn. Hệ thống cần trả về kết quả chất lượng cao với citation coverage tốt, đồng thời có thể trace được từng bước xử lý.

## Why multi-agent?

Single-agent (một LLM call duy nhất) có những hạn chế:

1. **Context overload**: Một agent phải vừa search, vừa phân tích, vừa viết — dễ bỏ sót hoặc loãng context khi query phức tạp.
2. **Không có chuyên môn hóa**: Mỗi bước (tìm nguồn, đánh giá, viết) cần prompt và temperature khác nhau. Single-agent không tối ưu được từng bước.
3. **Khó debug**: Khi output sai, không biết sai ở bước tìm kiếm, phân tích hay tổng hợp.
4. **Không có guardrail giữa các bước**: Không thể validate output trung gian trước khi chuyển sang bước tiếp.

Multi-agent giải quyết bằng cách tách vai trò rõ ràng, mỗi agent có prompt chuyên biệt, và shared state cho phép trace từng bước.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Routing: kiểm tra state, quyết định gọi agent nào tiếp theo, enforce max_iterations | ResearchState (toàn bộ) | route decision (researcher/analyst/writer/done) | Routing loop → max_iterations guardrail |
| Researcher | Tìm kiếm nguồn và tạo research notes | query + max_sources | sources[] + research_notes | Search API fail → static fallback |
| Analyst | Phân tích research notes: extract claims, compare viewpoints, flag weak evidence | research_notes + sources | analysis_notes | LLM timeout → tenacity retry 3 lần |
| Writer | Tổng hợp final answer với citations trỏ về sources | research_notes + analysis_notes + sources | final_answer (có [1],[2] refs) | LLM timeout → retry; thiếu data → viết với những gì có |
| Critic (bonus) | Fact-check final answer: citation coverage, consistency, hallucination risk | final_answer + research_notes + sources | critique findings | Optional — không block workflow |

## Shared state

`ResearchState` (Pydantic BaseModel) chứa:

| Field | Type | Lý do |
|---|---|---|
| `request` | ResearchQuery | Input gốc từ user — query, max_sources, audience |
| `iteration` | int | Đếm số lần supervisor chạy — cần cho max_iterations guardrail |
| `route_history` | list[str] | Ghi lại thứ tự routing — cần cho trace và debug |
| `sources` | list[SourceDocument] | Kết quả search từ Researcher — cần cho Analyst và Writer tham chiếu |
| `research_notes` | str \| None | Tóm tắt nguồn từ Researcher — Analyst dùng để phân tích |
| `analysis_notes` | str \| None | Phân tích từ Analyst — Writer dùng để viết final answer |
| `final_answer` | str \| None | Output cuối từ Writer — deliverable cho user |
| `agent_results` | list[AgentResult] | Log kết quả từng agent (content + metadata) — cần cho benchmark |
| `trace` | list[dict] | Trace events ghi lại mọi hành động — cần cho observability |
| `errors` | list[str] | Ghi lại lỗi nếu có — cần cho debugging |

## Routing policy

```
START → Supervisor
  ├─ Không có sources?        → Researcher → Supervisor
  ├─ Không có analysis_notes? → Analyst    → Supervisor
  ├─ Không có final_answer?   → Writer     → Supervisor
  ├─ Đủ hết?                  → DONE (END)
  └─ iteration >= max_iter?   → Writer (rush) hoặc DONE
```

Flow điển hình: `Supervisor → Researcher → Supervisor → Analyst → Supervisor → Writer → Supervisor → DONE` (4 iterations).

## Guardrails

- **Max iterations**: 6 (configurable via `MAX_ITERATIONS` env var, range 1-20). Supervisor check trước mỗi routing decision.
- **Timeout**: 60s per LLM call (configurable via `TIMEOUT_SECONDS`, range 5-600). Set trong OpenAI client constructor.
- **Retry**: 3 lần với exponential backoff (1s → 2s → 4s) qua `tenacity` decorator trên `LLMClient.complete()`.
- **Fallback**: SearchClient có 3 tầng fallback: Tavily API → LLM mock search → static results.
- **Validation**: Pydantic schemas validate tất cả input/output. `ResearchQuery.query` phải ≥ 5 ký tự.

## Benchmark plan

| Query | Metric | Expected outcome |
|---|---|---|
| "Research GraphRAG state-of-the-art and write a 500-word summary" | Latency, Cost, Quality (0-10), Citation coverage, Failure rate | Multi-agent chậm hơn 3-5x nhưng quality cao hơn 2-3 điểm |
| "Compare single-agent and multi-agent workflows for customer support" | Same metrics | Multi-agent có citation coverage tốt hơn |
| "Summarize production guardrails for LLM agents" | Same metrics | Cả hai nên pass, multi-agent có cấu trúc tốt hơn |
