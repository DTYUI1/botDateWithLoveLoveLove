import asyncio
import csv
import os
from dataclasses import dataclass, field


@dataclass
class StatsResult:
    samples: list[tuple[float, float]] = field(default_factory=list)

    def avg_cpu(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s[0] for s in self.samples) / len(self.samples)

    def max_mem_mb(self) -> float:
        return max((s[1] for s in self.samples), default=0.0)


def _parse_mem_to_mb(raw: str) -> float:
    raw = raw.strip().replace("iB", "B").upper()
    num_part = ""
    for ch in raw:
        if ch.isdigit() or ch == ".":
            num_part += ch
        else:
            break
    if not num_part:
        return 0.0
    value = float(num_part)
    unit = raw[len(num_part):]
    if unit.startswith("G"):
        return value * 1024.0
    if unit.startswith("K"):
        return value / 1024.0
    if unit.startswith("M"):
        return value
    if unit.startswith("B"):
        return value / (1024.0 * 1024.0)
    return value


async def _sample(container: str) -> tuple[float, float] | None:
    proc = await asyncio.create_subprocess_exec(
        "docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    line = out.decode().strip().splitlines()
    if not line:
        return None
    cpu_raw, mem_raw = line[0].split("|", 1)
    cpu = float(cpu_raw.strip().rstrip("%") or "0")
    mem_used = mem_raw.split("/", 1)[0].strip()
    return cpu, _parse_mem_to_mb(mem_used)


async def sampler(container: str, out_csv: str, stop: asyncio.Event, result: StatsResult) -> None:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_sec", "cpu_percent", "mem_mb"])
        t = 0
        while not stop.is_set():
            try:
                sample = await _sample(container)
                if sample is not None:
                    cpu, mem = sample
                    writer.writerow([t, f"{cpu:.2f}", f"{mem:.2f}"])
                    f.flush()
                    result.samples.append((cpu, mem))
            except Exception:
                pass
            t += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
