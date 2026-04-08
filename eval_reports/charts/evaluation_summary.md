# Evaluation Summary: Baseline vs. Multi-Agent RAG

| Metric | Baseline | Multi-Agent | Delta | p-value | Significant? |
|--------|----------|-------------|-------|---------|-------------|
| Fact Accuracy | 0.510 (0.444) | 0.570 (0.426) | +0.060 | 0.0496 | Yes * |
| Faithfulness | 0.627 (0.272) | 0.577 (0.238) | -0.050 | 0.1810 | No |
| Citation Recall | 0.417 (0.480) | 0.426 (0.486) | +0.009 | 0.7630 | No |
| Hallucination Score | 0.339 (0.246) | 0.427 (0.240) | +0.087 | 0.0155 | Yes * |

## Latency
| | Baseline | Multi-Agent |
|---|---------|-------------|
| Mean | 16.2s | 25.1s |
| p95 | 22.8s | 42.5s |