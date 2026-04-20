from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    sent: int = 0
    received: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def record_latency(self, sent_at: float, now: float) -> None:
        self.latencies_ms.append((now - sent_at) * 1000.0)
        self.received += 1

    def avg_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    def p95_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        idx = min(len(s) - 1, int(len(s) * 0.95))
        return s[idx]

    def max_ms(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0
