"""Generate evaluation charts comparing Baseline vs Multi-Agent RAG."""
import json
import os
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("WARNING: matplotlib not installed. Install with: pip install matplotlib")

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_reports")
CHARTS_DIR = os.path.join(EVAL_DIR, "charts")


def load_latest_results():
    """Load the most recent baseline and multi-agent results."""
    files = sorted(os.listdir(EVAL_DIR))
    baseline_files = [f for f in files if f.startswith("baseline_") and f.endswith(".json")]
    ma_files = [f for f in files if f.startswith("multi_agent_") and f.endswith(".json")]

    if not baseline_files or not ma_files:
        print("Need both baseline and multi_agent results.")
        return None, None

    with open(os.path.join(EVAL_DIR, baseline_files[-1])) as f:
        baseline = json.load(f)
    with open(os.path.join(EVAL_DIR, ma_files[-1])) as f:
        multi_agent = json.load(f)

    print(f"Loaded baseline:    {baseline_files[-1]} ({len(baseline)} queries)")
    print(f"Loaded multi-agent: {ma_files[-1]} ({len(multi_agent)} queries)")
    return baseline, multi_agent


def compute_stats(baseline, multi_agent):
    """Compute comparison statistics."""
    metrics = ["fact_accuracy", "faithfulness", "citation_recall", "hallucination_score"]
    stats = {}

    for metric in metrics:
        b = [r[metric] for r in baseline]
        m = [r[metric] for r in multi_agent]

        try:
            from scipy.stats import wilcoxon
            _, p_value = wilcoxon(m, b, alternative="two-sided")
        except Exception:
            p_value = 1.0

        stats[metric] = {
            "baseline_mean": np.mean(b), "baseline_std": np.std(b),
            "ma_mean": np.mean(m), "ma_std": np.std(m),
            "delta": np.mean(m) - np.mean(b),
            "p_value": p_value,
            "significant": p_value < 0.05,
        }

    stats["latency"] = {
        "baseline_mean": np.mean([r["latency_ms"] for r in baseline]),
        "ma_mean": np.mean([r["latency_ms"] for r in multi_agent]),
        "baseline_p95": np.percentile([r["latency_ms"] for r in baseline], 95),
        "ma_p95": np.percentile([r["latency_ms"] for r in multi_agent], 95),
    }

    return stats


def chart_metric_comparison(stats):
    """Bar chart: all metrics side by side."""
    metrics = ["fact_accuracy", "faithfulness", "citation_recall", "hallucination_score"]
    labels = ["Fact\nAccuracy", "Faithfulness", "Citation\nRecall", "Hallucination\nScore"]

    b_means = [stats[m]["baseline_mean"] for m in metrics]
    m_means = [stats[m]["ma_mean"] for m in metrics]
    b_stds = [stats[m]["baseline_std"] for m in metrics]
    m_stds = [stats[m]["ma_std"] for m in metrics]

    x = np.arange(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width / 2, b_means, width, yerr=b_stds, label="Baseline (Vector-Only)",
           color="#4A90D9", alpha=0.85, capsize=5)
    ax.bar(x + width / 2, m_means, width, yerr=m_stds, label="Multi-Agent RAG",
           color="#E8734A", alpha=0.85, capsize=5)

    for i, m in enumerate(metrics):
        if stats[m]["significant"]:
            y_max = max(b_means[i] + b_stds[i], m_means[i] + m_stds[i])
            ax.text(i, y_max + 0.05, "*", ha="center", fontsize=16, fontweight="bold")

    # Add delta labels
    for i in range(len(metrics)):
        delta = m_means[i] - b_means[i]
        color = "#2ECC71" if (delta > 0 and metrics[i] != "hallucination_score") or (delta < 0 and metrics[i] == "hallucination_score") else "#E74C3C"
        y_pos = max(b_means[i], m_means[i]) + max(b_stds[i], m_stds[i]) + 0.08
        ax.text(i, y_pos, f"{delta:+.3f}", ha="center", fontsize=9, color=color, fontweight="bold")

    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("RAG Evaluation: Baseline vs. Multi-Agent Pipeline", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 1.25)
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "metric_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def chart_radar(stats):
    """Radar chart comparing quality dimensions."""
    metrics = ["fact_accuracy", "faithfulness", "citation_recall"]
    labels = ["Fact Accuracy", "Faithfulness", "Citation Recall"]

    b_values = [stats[m]["baseline_mean"] for m in metrics]
    m_values = [stats[m]["ma_mean"] for m in metrics]
    b_values.append(1 - stats["hallucination_score"]["baseline_mean"])
    m_values.append(1 - stats["hallucination_score"]["ma_mean"])
    labels.append("Low Hallucination")

    b_values.append(b_values[0])
    m_values.append(m_values[0])

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles.append(angles[0])

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.plot(angles, b_values, "o-", linewidth=2, label="Baseline", color="#4A90D9")
    ax.fill(angles, b_values, alpha=0.15, color="#4A90D9")
    ax.plot(angles, m_values, "o-", linewidth=2, label="Multi-Agent", color="#E8734A")
    ax.fill(angles, m_values, alpha=0.15, color="#E8734A")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylim(0, 1.1)
    ax.set_title("RAG Quality Dimensions", fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=11)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "radar_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def chart_per_query_delta(baseline, multi_agent):
    """Per-query accuracy delta showing where each model wins."""
    n = len(baseline)
    b_acc = [r["fact_accuracy"] for r in baseline]
    m_acc = [r["fact_accuracy"] for r in multi_agent]
    deltas = [m - b for m, b in zip(m_acc, b_acc)]

    colors = ["#2ECC71" if d > 0.01 else "#E74C3C" if d < -0.01 else "#95A5A6" for d in deltas]

    wins = sum(1 for d in deltas if d > 0.01)
    losses = sum(1 for d in deltas if d < -0.01)
    ties = n - wins - losses

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(range(n), deltas, color=colors, alpha=0.8)
    ax.axhline(y=0, color="black", linewidth=0.8)
    ax.set_xlabel("Query ID", fontsize=11)
    ax.set_ylabel("Accuracy Delta (Multi-Agent - Baseline)", fontsize=11)
    ax.set_title(f"Per-Query Accuracy: Multi-Agent wins {wins}, Baseline wins {losses}, Ties {ties}",
                 fontsize=13, fontweight="bold")
    ax.set_xticks(range(n))
    ax.set_xticklabels([r.get("query_id", f"q{i+1:02d}") for i, r in enumerate(baseline)],
                       rotation=45, fontsize=7, ha="right")

    green_patch = mpatches.Patch(color="#2ECC71", label=f"Multi-Agent wins ({wins})")
    red_patch = mpatches.Patch(color="#E74C3C", label=f"Baseline wins ({losses})")
    gray_patch = mpatches.Patch(color="#95A5A6", label=f"Tie ({ties})")
    ax.legend(handles=[green_patch, red_patch, gray_patch], fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "per_query_delta.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def chart_latency(baseline, multi_agent):
    """Box plot comparing latency distributions."""
    b_lat = [r["latency_ms"] / 1000 for r in baseline]
    m_lat = [r["latency_ms"] / 1000 for r in multi_agent]

    fig, ax = plt.subplots(figsize=(8, 5))
    bp = ax.boxplot([b_lat, m_lat], labels=["Baseline\n(Vector-Only)", "Multi-Agent\nRAG"],
                    patch_artist=True, widths=0.5)
    bp["boxes"][0].set_facecolor("#4A90D9")
    bp["boxes"][0].set_alpha(0.6)
    bp["boxes"][1].set_facecolor("#E8734A")
    bp["boxes"][1].set_alpha(0.6)

    ax.set_ylabel("Latency (seconds)", fontsize=12)
    ax.set_title("Response Latency Distribution", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    ax.text(1, np.mean(b_lat) + 0.5, f"mean: {np.mean(b_lat):.1f}s", ha="center", fontsize=10)
    ax.text(2, np.mean(m_lat) + 0.5, f"mean: {np.mean(m_lat):.1f}s", ha="center", fontsize=10)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "latency_boxplot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def chart_progression():
    """Line chart showing metric improvement across iterations."""
    runs = [
        ("Baseline", "eval_reports/baseline_20260331_222115.json"),
        ("MA +Fixes", "eval_reports/multi_agent_20260401_150217.json"),
        ("MA +Graph", "eval_reports/multi_agent_20260401_212140.json"),
        ("MA +Coverage", "eval_reports/multi_agent_20260401_231130.json"),
    ]

    script_dir = os.path.dirname(__file__)
    data = {}
    for label, path in runs:
        full_path = os.path.join(script_dir, path)
        if os.path.exists(full_path):
            with open(full_path) as f:
                data[label] = json.load(f)

    if len(data) < 2:
        print("  Skipping progression chart (need at least 2 runs)")
        return

    metrics = ["fact_accuracy", "faithfulness", "citation_recall", "hallucination_score"]
    colors = {"fact_accuracy": "#2ECC71", "faithfulness": "#3498DB",
              "citation_recall": "#9B59B6", "hallucination_score": "#E74C3C"}
    display = {"fact_accuracy": "Fact Accuracy", "faithfulness": "Faithfulness",
               "citation_recall": "Citation Recall", "hallucination_score": "Hallucination"}

    fig, ax = plt.subplots(figsize=(10, 6))
    x_labels = list(data.keys())
    x = range(len(x_labels))

    for metric in metrics:
        values = [np.mean([r[metric] for r in data[label]]) for label in x_labels]
        style = "--" if metric == "hallucination_score" else "-"
        ax.plot(x, values, f"o{style}", linewidth=2, markersize=8,
                label=display[metric], color=colors[metric])
        # Add value labels
        for i, v in enumerate(values):
            ax.annotate(f"{v:.3f}", (i, v), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8, color=colors[metric])

    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels, fontsize=10)
    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Evaluation Metrics Across Iterations", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 0.85)
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(CHARTS_DIR, "progression.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {path}")


def generate_summary(stats):
    """Generate markdown summary."""
    lines = [
        "# Evaluation Summary: Baseline vs. Multi-Agent RAG",
        "",
        "| Metric | Baseline | Multi-Agent | Delta | p-value | Significant? |",
        "|--------|----------|-------------|-------|---------|-------------|",
    ]
    for metric in ["fact_accuracy", "faithfulness", "citation_recall", "hallucination_score"]:
        s = stats[metric]
        sig = "Yes *" if s["significant"] else "No"
        lines.append(
            f"| {metric.replace('_', ' ').title()} | "
            f"{s['baseline_mean']:.3f} ({s['baseline_std']:.3f}) | "
            f"{s['ma_mean']:.3f} ({s['ma_std']:.3f}) | "
            f"{s['delta']:+.3f} | {s['p_value']:.4f} | {sig} |"
        )

    lat = stats["latency"]
    lines.extend([
        "",
        "## Latency",
        "| | Baseline | Multi-Agent |",
        "|---|---------|-------------|",
        f"| Mean | {lat['baseline_mean']/1000:.1f}s | {lat['ma_mean']/1000:.1f}s |",
        f"| p95 | {lat['baseline_p95']/1000:.1f}s | {lat['ma_p95']/1000:.1f}s |",
    ])

    return "\n".join(lines)


def main():
    if not HAS_MPL:
        print("Cannot generate charts without matplotlib.")
        return

    os.makedirs(CHARTS_DIR, exist_ok=True)

    baseline, multi_agent = load_latest_results()
    if not baseline or not multi_agent:
        return

    stats = compute_stats(baseline, multi_agent)

    print("\nGenerating charts...")
    chart_metric_comparison(stats)
    chart_radar(stats)
    chart_per_query_delta(baseline, multi_agent)
    chart_latency(baseline, multi_agent)
    chart_progression()

    summary = generate_summary(stats)
    summary_path = os.path.join(EVAL_DIR, "evaluation_summary.md")
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"\n  Summary saved: {summary_path}")
    print(summary)


if __name__ == "__main__":
    main()
