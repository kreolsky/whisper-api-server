# Deployment: `green` node (RTX 5060) — duplicate ASR service

> Created: 2026-06-05. Audience: a maintainer/agent operating this service on `green`.
> Host-side (Proxmox/GPU passthrough) details live in the home-lab repo
> (`assistant-home-lab/docs/green-whisper.md`); this file is about running **this** project there.

## What this is

A second, duplicate instance of this transcription service, running on a dedicated VM
`green` so the lab no longer depends on the single ASR host `orange`. It serves the same
GigaAM-v3 Russian model over the same OpenAI-compatible API.

| Item | Value |
|------|-------|
| Node | VM `green` (VMID 112 on Proxmox host `black`) |
| Access | `ssh green` (ProxyJump through `black`) |
| IP / port | `10.10.1.21:5042` (static, cloud-init — not DHCP) |
| OS | Ubuntu 24.04 LTS |
| GPU | RTX 5060 (Blackwell, **sm_120**, 8 GB), PCIe passthrough, **power-capped to 123 W** |
| NVIDIA driver | 595.71.05 |
| Deploy dir | `/opt/whisper-api` (this repo's working copy) |
| Runtime | Docker Compose, container `whisper-api-whisper-api-1` |
| Model | GigaAM-v3 (`config.json` → `model_type: gigaam`), `device_id: 0` |
| API | `POST /v1/audio/transcriptions`, `GET /health` |

`orange` (RTX 3090) remains the primary; `green` is the redundant/secondary node.

## ⚠️ Critical: the repo defaults do NOT build on this card

The committed `requirements.txt` and `Dockerfile` target an **older stack** that fails on
RTX 5060 (Blackwell sm_120 / CUDA 13). The deployed copy on `green` carries local fixes that
are **not committed upstream**. A plain `git pull` + rebuild from repo HEAD will reintroduce
the breakage. Either commit these changes or preserve `green`'s local overrides.

Deltas applied on `green` (matching the proven `orange` environment):

| File | Repo default (broken on 5060) | `green` override |
|------|-------------------------------|------------------|
| `Dockerfile` base | `nvidia/cuda:12.8.1-cudnn9-runtime-ubuntu24.04` (tag no longer exists — NVIDIA renamed `cudnn9`→`cudnn`) | `nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04` |
| `torch` / `torchaudio` | `2.7.0+cu128` | `2.11.0+cu130` (+ `torchcodec==0.11.0`) |
| `pyannote-audio` | `>=3.1` (resolves to 3.4.0; rejects local segmentation dir → `HFValidationError`) | `==4.0.4` (requires `torch>=2.8`, hence the torch bump) |
| `transformers` | `4.49.0` | `4.51.3` |
| `accelerate` | `1.4.0` | `1.6.0` |
| `scipy` | `1.13.1` | `1.15.2` |
| `flash_attn` | `cu128torch2.7` wheel | unchanged (same wheel as orange; coexists with torch 2.11, gigaam path doesn't import it) |
| `docker-compose.yml` model volume | `/home/text-generation/models:...:ro` (absolute) | `./models:/home/text-generation/models:ro` (model lives in repo dir) |

Why: `pyannote-audio 4.x` (needed because 3.x can't load a local segmentation directory) pulls
`torch>=2.8`; the only consistent set that also supports sm_120 is the CUDA-13 / torch-2.11 stack
that `orange` already runs. See the Troubleshooting table for the exact errors.

## Model files

Model is **not** in git. On `green` it lives at:

```
/opt/whisper-api/models/whisper/gigaAM-v3/   (~435 MB: config.json, pytorch_model.bin,
                                              modeling_gigaam.py, tokenizer.model, segmentation/)
```

`docker-compose.yml` mounts `./models` → `/home/text-generation/models` (the path `config.json`
expects). Source of truth is `orange:/home/text-generation/models/whisper/`.

Refresh / add a model from orange (key already authorized green→orange):
```bash
ssh green
cd /opt/whisper-api
rsync -a -e 'ssh -o StrictHostKeyChecking=accept-new' \
  serge@10.10.1.20:/home/text-generation/models/whisper/gigaAM-v3 ./models/whisper/
```

## Operations runbook

All commands run on `green` (`ssh green`), docker needs `sudo`.

```bash
# status / health
sudo docker compose -f /opt/whisper-api/docker-compose.yml ps
curl -s http://127.0.0.1:5042/health           # 200 = up

# logs
sudo docker logs --tail 50 -f whisper-api-whisper-api-1

# restart (no rebuild)
cd /opt/whisper-api && sudo docker compose restart

# rebuild after editing requirements/Dockerfile  (heavy: pulls torch ~3 GB)
cd /opt/whisper-api && sudo docker compose up -d --build

# smoke test (any audio file present on green)
curl -s -F 'file=@/tmp/sample.webm' http://127.0.0.1:5042/v1/audio/transcriptions
```

GPU / power:
```bash
nvidia-smi                                    # expect RTX 5060, power.limit 123 W
sudo /usr/local/bin/gpu-power-limit.sh 123    # re-apply (123–145 W); persists via
systemctl status gpu-power-limits.service     #   gpu-power-limits.service on boot
```

## Troubleshooting (issues already hit during bring-up)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `... cudnn9-runtime ... not found` on build | NVIDIA removed the `cudnn9` tag | use `...-cudnn-runtime-...` |
| `OSError: libcudart.so.13: cannot open shared object file` | torchaudio resolved to 2.11 (CUDA 13) while torch was 2.7 (CUDA 12) | pin the whole stack to torch/torchaudio 2.11 + CUDA-13 base |
| `HFValidationError: Repo id must be ...` on `segmentation` path | `pyannote-audio` 3.x can't load a local segmentation dir | `pyannote-audio==4.0.4` |
| `ResolutionImpossible: pyannote-audio 4.0.4 depends on torch>=2.8.0` | torch pinned to 2.7 | bump torch to 2.11.0+cu130 |
| `no space left on device` during build | image (~22 GB) + torch/flash_attn exceeded the 48 GB disk | VM disk grown to 85 GB (`qm disk resize 112 scsi0 +40G` + `growpart`/`resize2fs`) |
| container `Restarting (1)` | model failed to load | `docker logs` the container; usually a model-path or dependency mismatch |

## Verification (recorded at deploy time)

- **GPU stress** (torch matmul in-container): correctness OK before/after load, sustained
  ~12.9 TFLOPS fp32, 100 % util, power pinned at 123 W, peak 67 °C, no XID errors → PASS.
- **Transcription parity**: identical output to `orange` on an 87 s clip (byte-for-byte text).
  Timing: `green` 4.25 s vs `orange` 2.40 s — expected, the 5060 is an entry-level card vs the
  3090 flagship (~2× fewer cores, ~½ the memory bandwidth) and is power-capped to 123 W.

## Notes for further work

- This card's strength is **low-precision tensor compute (FP8/FP4)**, not FP32/bandwidth. ASR
  (fp16/fp32, small model) does not exercise it; that's fine for a redundant STT node.
- If switching to a Whisper model: `large-v3-turbo` fits in 8 GB in fp16 (no quant needed).
  For real speedup consider faster-whisper/CTranslate2 int8 — but first confirm its prebuilt
  wheels support sm_120 / CUDA 13.
- DHCP reservation is intentionally **not** used; the IP is static via cloud-init.
