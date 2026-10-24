"""Reader-robustness runs on worlds T1-T2, third version of the run script. Reader settings, GPU
placement and the reuse of 154 earlier answers are documented in runs/queue_reader_robust.log. Configure any
machine-specific GPU scheduling locally before running these conditions; the calls to the GPU scheduler of the authors'
machine below are skipped where it does not exist.

The first attempt (runs/reader_robust_parallel.py) pinned a second Ollama server with CUDA_VISIBLE_DEVICES=0, but
Ollama also enumerates GPUs through Vulkan, ignored the pin there and placed both thinking-on models on the RTX 5060 Ti,
part of the Q8 model on the CPU. It ran 00:45-07:06 and answered 154 questions (kept: same model and settings; the
answers are reused from the call cache). Servers are now started with OLLAMA_VULKAN=0, which leaves only CUDA devices.

Phase A: server on the RTX 5080 only (CUDA 0, port 11435): Qwen3-14B Q4 thinking on (fits one GPU).
Phase B: server on both GPUs (CUDA 0,1, port 11436): Qwen3-14B Q8 thinking on, Gemma 4 31b, Qwen3-32B (each larger than
one GPU, so the model is split across the two).
Then the GPU gate is released and QUEUE DONE is written to runs/queue_reader_robust.log.
"""
import datetime
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
LOG = open(os.path.join(ROOT, "runs", "queue_reader_robust.log"), "a", encoding="utf-8")


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(s):
    LOG.write(f"{now()} {s}\n")
    LOG.flush()


def runs(reader):
    out = []
    for s in ("saga_v5_s7", "saga_v5_s8"):
        for m in ("mem:cmm4", "mem:pbm25", "hybrid"):
            c = f"python methods/run_eval.py --data {s} --density d16 --num_ctx 16384 --reader {reader} --method {m}"
            if m != "hybrid":
                c += " --builder claude:claude-haiku-4-5-20251001 --wait_only"
            out.append(c)
    return out


def server(devices, port, tag):
    env = dict(os.environ, OLLAMA_VULKAN="0", CUDA_VISIBLE_DEVICES=devices, OLLAMA_HOST=f"127.0.0.1:{port}")
    p = subprocess.Popen(["ollama", "serve"], env=env, stdout=open(f"runs/_ollama_{tag}.log", "a"),
                         stderr=subprocess.STDOUT)
    time.sleep(12)
    log(f"Ollama server {tag} (CUDA {devices}, port {port}, Vulkan off) pid {p.pid}")
    return p, dict(os.environ, OLLAMA_URL=f"http://127.0.0.1:{port}"), f"127.0.0.1:{port}"


def placement(host):
    r = subprocess.run("ollama ps", shell=True, capture_output=True, text=True, env=dict(os.environ, OLLAMA_HOST=host))
    g = subprocess.run("nvidia-smi --query-gpu=index,name,memory.used --format=csv,noheader", shell=True,
                       capture_output=True, text=True)
    log("placement: " + " | ".join(l.strip() for l in (r.stdout + g.stdout).splitlines() if l.strip()))


def run(cmd, env, host, check):
    log(f"START {cmd}")
    t0 = time.time()
    p = subprocess.Popen(cmd, shell=True, env=env)
    if check:
        time.sleep(150)  # model loaded and answering by now
        placement(host)
    p.wait()
    log(f"END rc={p.returncode} {time.time() - t0:.0f}s {cmd}")


log("PLAN v3 start")
srv, env, host = server("0", 11435, "gpu0")
for i, c in enumerate(runs("ollamathink:qwen3:14b")):
    run(c, env, host, check=(i == 0))
srv.terminate()
time.sleep(10)
# both GPUs are requested from the machine's GPU scheduler before the two-GPU phase (authors' machine only)
log("requesting GPUs 0,1 through the gate")
if os.path.exists("../../gpu_control/gpu_gate.py"):
    subprocess.run('python ../../gpu_control/gpu_gate.py request "reader robustness phase B (needs both GPUs)" --gpus 0,1', shell=True)
log("GPUs 0,1 granted")
srv, env, host = server("0,1", 11436, "both")
first = True
for reader in ("ollamathink:qwen3:14b-q8_0", "ollama:gemma4:31b-it-q4_K_M", "ollama:qwen3:32b-q4_K_M"):
    for i, c in enumerate(runs(reader)):
        run(c, env, host, check=(i == 0))
srv.terminate()
time.sleep(5)
if os.path.exists("../../gpu_control/gpu_gate.py"):
    subprocess.run("python ../../gpu_control/gpu_gate.py release", shell=True)
log("gpu gate released")
log("QUEUE DONE")
