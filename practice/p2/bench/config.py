import os


def _int_list(env_name: str, default: str) -> list[int]:
    raw = os.getenv(env_name, default)
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_QUEUE = "bench_q"

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_QUEUE = "bench_queue"

RABBITMQ_CONTAINER = os.getenv("RABBITMQ_CONTAINER", "p2-rabbitmq")
REDIS_CONTAINER = os.getenv("REDIS_CONTAINER", "p2-redis")

DURATION_SEC = int(os.getenv("BENCH_DURATION", "30"))
DRAIN_SEC = int(os.getenv("BENCH_DRAIN", "2"))

SIZES = _int_list("BENCH_SIZES", "128,1024,10240,102400")
RATES = _int_list("BENCH_RATES", "1000,5000,10000")
BROKERS = ("rabbitmq", "redis")

RESULTS_DIR = "/app/results"
RESULTS_CSV = f"{RESULTS_DIR}/results.csv"

DEGRADE_LOSS_RATIO = 0.05
DEGRADE_P95_MS = 500.0
DEGRADE_THROUGHPUT_RATIO = 0.8
