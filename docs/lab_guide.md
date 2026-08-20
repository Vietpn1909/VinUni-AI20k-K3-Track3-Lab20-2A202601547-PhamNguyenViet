# Lab Guide: Multi-Agent Research System

## Scenario

Bạn cần xây dựng một research assistant có thể nhận câu hỏi dài, tìm thông tin, phân tích và viết câu trả lời cuối cùng. Lab yêu cầu so sánh hai cách làm:

1. **Single-agent baseline**: một agent làm toàn bộ.
2. **Multi-agent workflow**: Supervisor điều phối Researcher, Analyst, Writer.

## Quy tắc quan trọng

- Không thêm agent nếu không có lý do rõ ràng.
- Mỗi agent phải có responsibility riêng.
- Shared state phải đủ rõ để debug.
- Phải có trace hoặc log cho từng bước.
- Phải benchmark, không chỉ nhìn output bằng cảm tính.

## Milestone 1: Baseline

File gợi ý:

- `src/multi_agent_research_lab/cli.py`
- `src/multi_agent_research_lab/services/llm_client.py`

DONE: thay baseline placeholder bằng một call LLM thật.

## Milestone 2: Supervisor

File gợi ý:

- `src/multi_agent_research_lab/agents/supervisor.py`
- `src/multi_agent_research_lab/graph/workflow.py`

DONE: implement routing policy.

Gợi ý câu hỏi thiết kế:

- Khi nào gọi Researcher?
- Khi nào gọi Analyst?
- Khi nào gọi Writer?
- Khi nào stop?
- Nếu agent fail thì retry hay fallback?

## Milestone 3: Worker agents

File gợi ý:

- `src/multi_agent_research_lab/agents/researcher.py`
- `src/multi_agent_research_lab/agents/analyst.py`
- `src/multi_agent_research_lab/agents/writer.py`

DONE: implement từng worker.

## Milestone 4: Trace và benchmark

File gợi ý:

- `src/multi_agent_research_lab/observability/tracing.py`
- `src/multi_agent_research_lab/evaluation/benchmark.py`
- `src/multi_agent_research_lab/evaluation/report.py`

Benchmark tối thiểu:

| Metric | Cách đo gợi ý |
|---|---|
| Latency | wall-clock time |
| Cost | token usage hoặc provider usage |
| Quality | rubric 0-10 do peer review |
| Citation coverage | số claims có source / tổng claims chính |
| Failure rate | số query fail / tổng query |

## Troubleshooting

### macOS: lỗi SSL certificate khi gọi API qua HTTPS (Tavily, OpenAI, ...)

Triệu chứng: khi implement `SearchClient` (hoặc bất kỳ HTTPS call nào) trên macOS, bạn có thể gặp lỗi kiểu:

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate
```

Nguyên nhân: Python cài từ python.org trên macOS **không dùng** certificate store của hệ điều hành, nên không tìm thấy CA bundle hợp lệ. Đây là lỗi môi trường, **không phải** do API key sai.

Cách khắc phục (chọn 1 trong 3):

1. **Chạy script cài certificate đi kèm Python** (nhanh nhất):

   ```bash
   /Applications/Python\ 3.12/Install\ Certificates.command
   ```

   (thay `3.12` bằng version Python của bạn)

2. **Dùng `certifi` trong code** — thêm `certifi` vào dependencies, rồi tạo SSL context khi gọi HTTPS:

   ```python
   import certifi
   import ssl
   from urllib.request import urlopen

   ssl_context = ssl.create_default_context(cafile=certifi.where())
   urlopen(request, timeout=timeout, context=ssl_context)
   ```

3. **Set biến môi trường** trỏ tới CA bundle của certifi (không cần đổi code):

   ```bash
   export SSL_CERT_FILE=$(python -m certifi)
   ```

## Exit ticket

Mỗi nhóm trả lời 2 câu:

### 1. Case nào nên dùng multi-agent? Vì sao?

**Nên dùng multi-agent khi task phức tạp, cần nhiều bước xử lý với yêu cầu chất lượng khác nhau:**

- **Research tổng hợp từ nhiều nguồn**: Cần tìm → phân tích → viết. Mỗi bước cần prompt và temperature riêng (researcher cần factual/low temp, writer cần creative/higher temp). Trong lab, multi-agent cho citation coverage tốt hơn vì Researcher chuyên tìm nguồn, Analyst chuyên đánh giá, Writer chuyên tổng hợp.
- **Task cần validation trung gian**: Supervisor kiểm tra output từng bước trước khi chuyển tiếp. Nếu Researcher không tìm được source, không gọi Analyst vô nghĩa.
- **Hệ thống cần debug/trace rõ ràng**: Khi output cuối sai, shared state + route_history cho phép trace ngược: sai ở bước search (nguồn kém), phân tích (logic sai), hay tổng hợp (hallucination). Single-agent không có khả năng này.
- **Ví dụ cụ thể từ lab**: Query "Research GraphRAG state-of-the-art" — multi-agent cho ra bài viết có structure (headings, citations [1]-[5], references section) với quality score 9-10/10, trong khi baseline chỉ cho paragraph đơn giản quality 4-5/10.

### 2. Case nào không nên dùng multi-agent? Vì sao?

**Không nên dùng multi-agent khi ưu tiên tốc độ, chi phí, hoặc task đơn giản:**

- **Query đơn giản, trả lời ngắn**: "GraphRAG là gì?" — single-agent trả lời trong 3s với $0.00007. Multi-agent tốn 30s và $0.002 (gấp ~10x thời gian, ~28x chi phí) cho cùng một câu hỏi đơn giản, mà chất lượng không cải thiện tương xứng.
- **Ứng dụng real-time / latency-sensitive**: Chatbot, customer support — user không chờ được 30s. Multi-agent có latency cộng dồn từ nhiều LLM calls tuần tự.
- **Budget giới hạn**: Multi-agent tốn 4+ LLM calls vs 1 call. Nếu chạy 1000 queries/ngày, chi phí gấp 4-5x.
- **Khi không cần trace/audit**: Nếu output chỉ cần "đủ tốt" và không ai cần biết tại sao model trả lời như vậy, overhead của multi-agent không đáng.
- **Bài học từ lab**: Trade-off chính là **quality vs (latency + cost)**. Multi-agent không phải lúc nào cũng thắng — cần benchmark để quyết định, không dùng cảm tính.

