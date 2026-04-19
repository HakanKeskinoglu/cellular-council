# 🧬 CCA Framework — Detaylı Uygulama Planı

README'de tanımlanan vizyonu tam olarak gerçekleştirmek için kapsamlı bir uygulama planı.

---

## Mevcut Durum Analizi

### ✅ Tamamlanmış (Çalışan Kod)

| Modül | Dosya | Satır | Durum |
|-------|-------|-------|-------|
| **Core Types** | `cca/core/__init__.py` | 198 | ✅ Tam — CellOutput, CouncilDecision, CellRole, enums |
| **BaseCell** | `cca/cells/base.py` | 352 | ✅ Tam — analyze, debate, health, retry logic |
| **Specialized Cells** | `cca/cells/specialized.py` | 334 | ✅ Risk, Ethics, Technical, Financial, Security + factory |
| **Council Orchestrator** | `cca/core/council.py` | 375 | ✅ Tam — deliberate, debate rounds, cell management |
| **Consensus Engine** | `cca/consensus/engine.py` | 429 | ✅ 5 strateji: Weighted, Majority, Unanimous, Apex, Delphi |
| **LLM Backends** | `cca/llm/backends.py` | 262 | ✅ Ollama, OpenAI, Anthropic |
| **Apex Layer** | `cca/apex/layer.py` | 134 | ✅ LLM-based synthesis |
| **Cluster Manager** | `cca/cluster/manager.py` | 177 | ✅ Multi-round debate orchestration |
| **Health Monitor** | `cca/health/monitor.py` | 141 | ✅ Cell health tracking, degradation detection |
| **AlertMind Example** | `examples/alertmind/alarm_decision.py` | 329 | ✅ NetworkAlarmCell, HardwareAlarmCell, DataCenterAlarm |
| **Unit Tests** | `tests/unit/test_core.py` | 297 | ✅ 21 test — MockLLMBackend |

### ⚠️ Stub / Minimal (Kod var ama yetersiz)

| Modül | Dosya | Durum |
|-------|-------|-------|
| **Synapse Protocol** | `cca/synapse/protocol.py` | 26 satır — sadece Message, MessageType, minimal Synapse sınıfı |
| **Advisors** | `cca/advisors/base.py` | 22 satır — sadece BaseAdvisor abstract + AdvisorRole enum |

### ❌ README'de Var Ama Kod Yok

| Feature | README Referans |
|---------|----------------|
| **StemCell** | CellRole.STEM tanımlı ama sınıf yok |
| **Sub-Cell Spawning** | README'de detaylı mimari + kod örneği var |
| **Synapse Visualization (WebSocket)** | Roadmap'te `[ ]` |
| **Health Monitoring Dashboard** | Roadmap'te `[ ]` |
| **CLI** | `pyproject.toml`'da `cca = "cca.cli:main"` tanımlı ama `cli.py` yok |
| **Async Streaming** | Roadmap'te `[ ]` |
| **Docker Compose** | Roadmap'te `[ ]` |
| **PyPI Publication** | Roadmap'te `[ ]` |
| **Flutter Mobile Template** | Roadmap'te `[ ]` — ayrı proje, bu plana dahil değil |

---

## Önerilen Faz Planı

```
Phase 1: Stub Tamamlama (Core Eksikler)       ██████░░░░  ~3 gün
Phase 2: Synapse Layer Tam Implementasyonu     ████░░░░░░  ~2 gün
Phase 3: CLI Module                            ██░░░░░░░░  ~1 gün
Phase 4: Async Streaming Decisions             ██░░░░░░░░  ~1 gün
Phase 5: Altyapı (Docker + PyPI)               ████░░░░░░  ~2 gün
Phase 6: Health Monitoring Dashboard           ████░░░░░░  ~2 gün
Phase 7: Test Genişletme                       ████░░░░░░  ~2 gün
```

---

## Phase 1: Stub Tamamlama (Core Eksikler)

En kritik eksikler — README'de açıkça tanımlanan ama kodu olmayan bileşenler.

---

### 1.1 — Advisors Tam Implementasyonu

#### [MODIFY] `cca/advisors/base.py`

Mevcut 22-satırlık stub'ı tam implementasyona çevir:

- `BaseAdvisor` sınıfını genişlet: `id`, `weight=0` (advisory, oy hakkı yok), `system_prompt` property
- `advise()` metodu: tüm cell output'larını okuyup non-binding tavsiye üretsin
- Health tracking ekle (analyzer ile aynı pattern)

#### [NEW] `cca/advisors/specialized.py`

Built-in advisor rolleri:

```python
class EthicsAuditor(BaseAdvisor):
    """Bağımsız etik denetim — cell'lerin kararlarını etik açıdan gözden geçirir."""

class RiskAuditor(BaseAdvisor):
    """Risk cell'inin kör noktalarını kontrol eder."""

class ProcessMonitor(BaseAdvisor):
    """Deliberation sürecinin kalitesini izler — yanlılık, groupthink tespiti."""
```

#### [MODIFY] `cca/core/council.py`

- `add_advisor()` metodu ekle
- `deliberate()` akışına advisor çağrısı entegre et:
  - Cell çıktıları toplandıktan SONRA, consensus ÖNCE
  - Advisor notları `advisory_notes` olarak CouncilDecision'a eklensin
- Advisor çıktılarını consensus engine'e `advisory_outputs` parametresiyle taşı

---

### 1.2 — StemCell Implementasyonu

#### [NEW] `cca/cells/stem.py`

README'deki mimari şemadan birebir:

```python
class StemCell(BaseCell):
    """Undifferentiated cell — runtime'da uzmanlaştırılır."""

    def __init__(self, llm_backend, **kwargs):
        super().__init__(role=CellRole.STEM, llm_backend=llm_backend, **kwargs)
        self._dynamic_role: str | None = None
        self._system_prompt: str | None = None
        self._differentiated: bool = False

    async def differentiate(
        self,
        role: str,
        context: dict | None = None,
        regulations: list[str] | None = None,
    ) -> "StemCell":
        """Runtime'da dinamik system prompt oluşturarak uzmanlaştır."""
        self._state = CellState.DIFFERENTIATING
        self._dynamic_role = role
        self._system_prompt = self._generate_system_prompt(role, context, regulations)
        self._differentiated = True
        self._state = CellState.ACTIVE
        return self

    def _generate_system_prompt(self, role, context, regulations) -> str:
        """Template-based prompt generation (Paper 4 recommendation)."""
        # İlk versiyon: template fill — meta-LLM call değil
        ...

    @property
    def system_prompt(self) -> str:
        if not self._differentiated:
            raise RuntimeError("StemCell must be differentiated before use")
        return self._system_prompt

    async def analyze(self, query, context=None) -> CellOutput:
        if not self._differentiated:
            raise RuntimeError("StemCell must be differentiated before use")
        return await self._call_llm(query, context)

    def reset(self):
        """Hücreyi pool'a geri gönder — after session recycling."""
        self._dynamic_role = None
        self._system_prompt = None
        self._differentiated = False
        self._state = CellState.DORMANT
```

#### [NEW] `cca/cells/pool.py`

StemCell havuzu:

```python
class StemCellPool:
    """Pre-allocated StemCell pool for on-demand differentiation."""

    def __init__(self, llm_backend, pool_size: int = 5): ...
    def acquire(self) -> StemCell: ...
    def release(self, cell: StemCell): ...  # reset + return to pool
```

---

### 1.3 — Sub-Cell Spawning

#### [MODIFY] `cca/cells/base.py`

BaseCell'e spawning yeteneği ekle:

```python
class BaseCell(ABC):
    MAX_DEPTH = 2  # Sınıf seviyesi güvenlik sınırı

    def __init__(self, ..., depth: int = 0):
        self.depth = depth
        ...

    def _requires_sub_council(self, query: str) -> bool:
        """Override edilebilir: alt konsey gerekip gerekmediğine karar verir."""
        return False  # Default: alt konsey kullanma

    async def _spawn_sub_council(
        self,
        query: str,
        context: dict | None,
        cells: list[tuple[CellRole, float]],
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY_VOTE,
    ) -> CellOutput:
        """Alt konsey oluştur, deliberate et, sonucu CellOutput olarak dön."""
        if self.depth >= self.MAX_DEPTH:
            raise RuntimeError(f"Max depth {self.MAX_DEPTH} exceeded")

        from cca.core.council import Council
        sub = Council(
            name=f"{self.role.value}_sub_council",
            llm_backend=self.llm,
            strategy=strategy,
            debate_rounds=0,
        )
        for role, weight in cells:
            sub.add_cell(role, weight=weight)

        decision = await sub.deliberate(query, context)
        return CellOutput.from_decision(decision, source_role=self.role, source_id=self.id)
```

#### [MODIFY] `cca/core/__init__.py`

`CellOutput`'a class method ekle:

```python
class CellOutput(BaseModel):
    @classmethod
    def from_decision(cls, decision: "CouncilDecision", source_role: CellRole, source_id: str) -> "CellOutput":
        """CouncilDecision'ı tek bir CellOutput'a dönüştür (alt konsey → üst konsey)."""
        ...
```

---

## Phase 2: Synapse Layer Tam Implementasyonu

---

### 2.1 — Full Synapse Protocol

#### [MODIFY] `cca/synapse/protocol.py`

26-satırlık stub'ı tam bir event bus'a çevir:

```python
class SynapseMessage(BaseModel):
    """Hücreler arası iletişim mesajı."""
    id: str
    sender_id: str
    receiver_id: str | None  # None = broadcast
    message_type: MessageType
    signal_type: SignalType
    payload: dict
    timestamp: datetime
    round_number: int = 1
    metadata: dict = {}

class Synapse:
    """Merkezi iletişim veri yolu — tüm hücre-hücre mesajlaşmasını yönetir."""

    def __init__(self):
        self._messages: list[SynapseMessage] = []
        self._subscribers: dict[str, list[Callable]] = {}

    def send(self, message: SynapseMessage) -> None: ...
    def receive(self, receiver_id: str) -> list[SynapseMessage]: ...
    def subscribe(self, cell_id: str, callback: Callable) -> None: ...
    def broadcast(self, message: SynapseMessage) -> None: ...
    def history(self, session_id: str | None = None) -> list[SynapseMessage]: ...
    def export_timeline(self) -> list[dict]: ...
```

### 2.2 — Synapse Visualization Layer

#### [NEW] `cca/synapse/visualization.py`

WebSocket tabanlı canlı izleme:

```python
class SynapseVisualizer:
    """WebSocket ile canlı deliberation akışını görselleştirir."""

    def __init__(self, synapse: Synapse, port: int = 8765): ...
    async def start_server(self): ...
    async def broadcast_event(self, event: dict): ...
```

> **Not:** WebSocket server basit bir `websockets` kütüphanesi ile uygulanacak. Frontend tarafı Phase 6'da (Dashboard) eklenecek.

---

## Phase 3: CLI Module

---

#### [NEW] `cca/cli.py`

`pyproject.toml` zaten `cca = "cca.cli:main"` tanımlıyor ama dosya yok:

```python
"""CCA Command-Line Interface."""
import asyncio
import click

@click.group()
def main():
    """🧬 Cellular Council Architecture — CLI"""
    pass

@main.command()
@click.option("--model", default="llama3.2", help="Ollama model name")
@click.option("--strategy", default="weighted_average", type=click.Choice([...]))
@click.option("--debate-rounds", default=1, type=int)
@click.argument("query")
def deliberate(model, strategy, debate_rounds, query):
    """Run a deliberation on a query."""
    ...

@main.command()
def health():
    """Check LLM backend health status."""
    ...

@main.command()
@click.argument("alarm_file", type=click.Path(exists=True))
def alertmind(alarm_file):
    """Process alarms from a JSON file through AlertMind."""
    ...

@main.command()
def info():
    """Show CCA version and configuration."""
    ...
```

> **Önemli:** `click` bağımlılığı `pyproject.toml`'a eklenmeli: `"click>=8.0"`

---

## Phase 4: Async Streaming Decisions

---

#### [NEW] `cca/core/streaming.py`

Deliberation sürecini gerçek zamanlı olarak stream eden API:

```python
class StreamingCouncil(Council):
    """Council subclass adding async generator based streaming."""

    async def deliberate_stream(
        self, query: str, context: dict | None = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Yields events as deliberation progresses."""
        yield StreamEvent(type="session_start", ...)
        # Round 1
        for cell in self._cells.values():
            output = await cell.analyze(query, context)
            yield StreamEvent(type="cell_output", data=output)
        # Debate rounds...
        yield StreamEvent(type="consensus", data=result)
        yield StreamEvent(type="decision", data=decision)
```

---

## Phase 5: Altyapı (Docker + PyPI)

---

### 5.1 — Docker Compose

#### [NEW] `Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY cca/ cca/
RUN pip install --no-cache-dir ".[all]"
ENTRYPOINT ["cca"]
```

#### [NEW] `docker-compose.yml`

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]

  cca:
    build: .
    depends_on: [ollama]
    environment:
      - OLLAMA_HOST=http://ollama:11434

  dashboard:
    build:
      context: .
      dockerfile: Dockerfile.dashboard
    ports: ["8080:8080"]
    depends_on: [cca]
```

### 5.2 — PyPI Hazırlık

#### [MODIFY] `pyproject.toml`

- `click` bağımlılığı ekle
- `websockets` optional ekle: `viz = ["websockets>=12.0"]`
- `HakanKeskinoglu` placeholder'larını güncelle
- Publish workflow için `[tool.hatch.build]` ayarlarını kontrol et

#### [NEW] `.github/workflows/publish.yml`

PyPI publish GitHub Action — tag push tetiklemeli.

---

## Phase 6: Health Monitoring Dashboard

---

#### [NEW] `cca/dashboard/`

Minimal web dashboard (tek HTML + JS):

```
cca/dashboard/
├── __init__.py
├── server.py       # FastAPI/aiohttp server
├── static/
│   ├── index.html  # Dashboard UI
│   ├── app.js      # WebSocket client + visualization
│   └── style.css   # Dashboard styling
```

**Dashboard özellikleri:**
- Cell health durumlarını canlı göster (yeşil/sarı/kırmızı)
- Deliberation timeline (hangi cell ne zaman çıktı verdi)
- Consensus score bar chart
- Synapse mesajları timeline view

---

## Phase 7: Test Genişletme

---

### Yeni Test Dosyaları

| Test Dosyası | Kapsam |
|-------------|--------|
| `tests/unit/test_advisors.py` | Advisor oluşturma, advise çağrısı, non-voting doğrulaması |
| `tests/unit/test_stem_cell.py` | StemCell differentiation, reset, pool acquire/release |
| `tests/unit/test_sub_council.py` | Sub-cell spawning, max_depth guard, CellOutput.from_decision |
| `tests/unit/test_synapse.py` | Full synapse: send, receive, subscribe, history, export |
| `tests/unit/test_streaming.py` | StreamingCouncil event sequence doğrulaması |
| `tests/unit/test_cli.py` | CLI komutları (click.testing.CliRunner) |
| `tests/integration/test_full_pipeline.py` | End-to-end: alarm → council → decision (MockLLM) |
| `tests/integration/test_alertmind.py` | AlertMind example'ın tam çalışma testi |

**Hedef Coverage:** ≥ 85%

---

## Doğrulama Planı

### Otomatik Testler

```bash
# Her phase sonrası
pytest tests/ -v --cov=cca --cov-report=term-missing

# Lint
ruff check cca/

# Type checking
mypy cca/

# CLI test (Phase 3 sonrası)
cca info
cca deliberate --model llama3.2 "test query"
```

### Manuel Doğrulama

- Ollama çalışıyorken tam deliberation testi
- AlertMind example'ın gerçek alarm verisiyle testi
- Dashboard WebSocket bağlantı testi (Phase 6)

---

## Açık Sorular

1. **Flutter dahil mi?** — Ayrı proje olarak değerlendirdik, gerekirse dahil edilebilir
2. **Dashboard**: Web tabanlı mı, CLI tabanlı (rich) mı?
3. **asyncio-mqtt**: `pyproject.toml`'da var ama hiç kullanılmıyor — kaldırılmalı mı?
4. **StemCell prompt**: Template-fill mi yoksa meta-LLM call mı?
5. **GitHub kullanıcı adı**: `HakanKeskinoglu` placeholder'ı ne ile değiştirilecek?
6. **Faz önceliği**: Önerilen sıra: Phase 1 → 2 → 7 → 3 → 4 → 5 → 6
