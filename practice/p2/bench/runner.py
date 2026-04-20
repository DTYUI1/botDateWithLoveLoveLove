import asyncio
import csv
import os
from dataclasses import asdict, dataclass

from tabulate import tabulate

from bench import config, docker_stats, rabbit, redis_bench
from bench.metrics import RunMetrics


@dataclass
class RunResult:
    broker: str
    size_b: int
    target_rate: int
    sent: int
    received: int
    lost_pct: float
    throughput: float
    avg_ms: float
    p95_ms: float
    max_ms: float
    errors: int
    backlog: int
    cpu_pct: float
    mem_mb: float
    status: str


def _status(target_rate: int, sent: int, received: int, p95: float, throughput: float) -> str:
    if sent == 0:
        return "ERROR"
    loss_ratio = (sent - received) / sent
    if loss_ratio > config.DEGRADE_LOSS_RATIO:
        return "DEGRADED"
    if p95 > config.DEGRADE_P95_MS:
        return "DEGRADED"
    if throughput < target_rate * config.DEGRADE_THROUGHPUT_RATIO:
        return "DEGRADED"
    return "OK"


def _backend(broker: str):
    return rabbit if broker == "rabbitmq" else redis_bench


def _container(broker: str) -> str:
    return config.RABBITMQ_CONTAINER if broker == "rabbitmq" else config.REDIS_CONTAINER


async def run_one(broker: str, size: int, rate: int) -> RunResult:
    backend = _backend(broker)
    metrics = RunMetrics()

    await backend.purge()

    stop_producer = asyncio.Event()
    stop_consumer = asyncio.Event()
    stop_stats = asyncio.Event()

    stats_out = f"{config.RESULTS_DIR}/stats_{broker}_{size}_{rate}.csv"
    stats_result = docker_stats.StatsResult()
    stats_task = asyncio.create_task(
        docker_stats.sampler(_container(broker), stats_out, stop_stats, stats_result)
    )

    consumer_task = asyncio.create_task(backend.consumer(metrics, stop_consumer))
    producer_task = asyncio.create_task(backend.producer(rate, size, metrics, stop_producer))

    await asyncio.sleep(config.DURATION_SEC)
    stop_producer.set()
    try:
        await asyncio.wait_for(producer_task, timeout=5)
    except asyncio.TimeoutError:
        producer_task.cancel()

    await asyncio.sleep(config.DRAIN_SEC)
    stop_consumer.set()
    try:
        await asyncio.wait_for(consumer_task, timeout=5)
    except asyncio.TimeoutError:
        consumer_task.cancel()

    stop_stats.set()
    try:
        await asyncio.wait_for(stats_task, timeout=5)
    except asyncio.TimeoutError:
        stats_task.cancel()

    try:
        backlog = await backend.queue_size()
    except Exception:
        backlog = -1

    throughput = metrics.received / config.DURATION_SEC if config.DURATION_SEC else 0.0
    lost_pct = ((metrics.sent - metrics.received) / metrics.sent * 100.0) if metrics.sent else 0.0

    return RunResult(
        broker=broker,
        size_b=size,
        target_rate=rate,
        sent=metrics.sent,
        received=metrics.received,
        lost_pct=round(lost_pct, 2),
        throughput=round(throughput, 1),
        avg_ms=round(metrics.avg_ms(), 2),
        p95_ms=round(metrics.p95_ms(), 2),
        max_ms=round(metrics.max_ms(), 2),
        errors=metrics.errors,
        backlog=backlog,
        cpu_pct=round(stats_result.avg_cpu(), 1),
        mem_mb=round(stats_result.max_mem_mb(), 1),
        status=_status(rate, metrics.sent, metrics.received, metrics.p95_ms(), throughput),
    )


def _write_csv(results: list[RunResult]) -> None:
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    with open(config.RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def _print_table(results: list[RunResult]) -> None:
    rows = [
        [
            r.broker,
            r.size_b,
            r.target_rate,
            r.sent,
            r.received,
            f"{r.lost_pct}%",
            r.throughput,
            r.avg_ms,
            r.p95_ms,
            f"{r.cpu_pct}%",
            r.mem_mb,
            r.status,
        ]
        for r in results
    ]
    headers = [
        "broker", "size", "rate",
        "sent", "recv", "lost",
        "thr/s", "avg ms", "p95 ms",
        "cpu", "mem MB", "status",
    ]
    print("\n" + tabulate(rows, headers=headers, tablefmt="github"))


def _print_summary(results: list[RunResult]) -> None:
    print("\n=== ВЫВОДЫ ===")

    by_broker: dict[str, list[RunResult]] = {}
    for r in results:
        by_broker.setdefault(r.broker, []).append(r)

    print("\nМаксимальная пропускная способность (throughput):")
    for broker, rs in by_broker.items():
        best = max(rs, key=lambda x: x.throughput)
        print(f"  {broker:<9}: {best.throughput} msg/sec @ size={best.size_b}B, target={best.target_rate}")

    print("\nПервая точка деградации single instance:")
    for broker, rs in by_broker.items():
        deg = [r for r in rs if r.status == "DEGRADED"]
        if deg:
            first = min(deg, key=lambda x: (x.size_b, x.target_rate))
            print(f"  {broker:<9}: size={first.size_b}B, rate={first.target_rate} (p95={first.p95_ms}ms, lost={first.lost_pct}%)")
        else:
            print(f"  {broker:<9}: не деградировал в пределах матрицы")

    print("\nЛучший на маленьких сообщениях (128B):")
    small = [r for r in results if r.size_b == 128 and r.status != "ERROR"]
    if small:
        best = max(small, key=lambda x: x.throughput)
        print(f"  {best.broker} — throughput {best.throughput} msg/sec (avg={best.avg_ms}ms, p95={best.p95_ms}ms)")

    print("\nЛучший на больших сообщениях (100KB):")
    big = [r for r in results if r.size_b == 102400 and r.status != "ERROR"]
    if big:
        best = max(big, key=lambda x: x.throughput)
        print(f"  {best.broker} — throughput {best.throughput} msg/sec (avg={best.avg_ms}ms, p95={best.p95_ms}ms)")


async def main() -> None:
    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    print(f"Duration/run: {config.DURATION_SEC}s, sizes={config.SIZES}, rates={config.RATES}")
    print(f"Total runs: {len(config.BROKERS) * len(config.SIZES) * len(config.RATES)}\n")

    results: list[RunResult] = []
    run_idx = 0
    total = len(config.BROKERS) * len(config.SIZES) * len(config.RATES)

    for broker in config.BROKERS:
        for size in config.SIZES:
            for rate in config.RATES:
                run_idx += 1
                print(f"[{run_idx}/{total}] {broker} | size={size}B | rate={rate}/s ...", flush=True)
                result = await run_one(broker, size, rate)
                results.append(result)
                print(f"    sent={result.sent} recv={result.received} lost={result.lost_pct}% "
                      f"thr={result.throughput}/s p95={result.p95_ms}ms cpu={result.cpu_pct}% "
                      f"mem={result.mem_mb}MB -> {result.status}")

    _write_csv(results)
    _print_table(results)
    _print_summary(results)
    print(f"\nCSV: {config.RESULTS_CSV}")


if __name__ == "__main__":
    asyncio.run(main())
