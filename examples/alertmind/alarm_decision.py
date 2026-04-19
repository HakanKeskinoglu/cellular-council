"""
AlertMind Decision Module Example
===================================

This example demonstrates CCA applied to data center alarm management —
the first real-world application of the Cellular Council Architecture.

Scenario: An air-gapped data center receives thousands of alarms daily.
The AlertMind Decision Module uses a local CCA council (powered by Ollama)
to intelligently classify, prioritize, and recommend actions for alarms.

Run this example:
    # Start Ollama with a local model first:
    # $ ollama pull llama3.2
    # $ ollama serve

    python examples/alertmind/alarm_decision.py

Architecture
------------
    ALARM EVENT
        │
        ▼
    ┌───────────────────────────────────────┐
    │         AlertMind Council             │
    │                                       │
    │  ┌──────────┐  ┌──────────┐           │
    │  │  Risk    │  │Technical │           │
    │  │  Cell    │  │  Cell    │           │
    │  └──────────┘  └──────────┘           │
    │  ┌──────────┐  ┌──────────┐           │
    │  │Security  │  │Operations│           │
    │  │  Cell    │  │  Cell    │           │
    │  └──────────┘  └──────────┘           │
    │                                       │
    │  ──→  Consensus (APEX_OVERRIDE)  ──→  │
    └───────────────────────────────────────┘
        │
        ▼
    AlarmDecision (severity, action, priority)
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Add parent directory to path for development use
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cca import Council
from cca.cells.base import BaseCell, CellRole
from cca.core import CellOutput, SignalType, ConsensusStrategy
from cca.llm.backends import OllamaBackend


# ---------------------------------------------------------------------------
# Domain-specific cells for data center alarm management
# ---------------------------------------------------------------------------

class NetworkAlarmCell(BaseCell):
    """Specialized for network-related alarm analysis."""

    def __init__(self, llm_backend, **kwargs):
        super().__init__(role=CellRole.TECHNICAL, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are a NETWORK OPERATIONS SPECIALIST in a data center alarm council.

Your expertise: network infrastructure, BGP/OSPF routing, switch/router failures,
bandwidth saturation, packet loss, latency spikes, interface flapping, VLAN issues.

When analyzing alarms:
- Identify the affected network layer (L1/L2/L3/L4)
- Estimate blast radius (how many systems/users affected)
- Determine if this is a symptom or root cause
- Recommend immediate network-level action

ALWAYS respond in this exact format:
ANALYSIS: [network-specific analysis]
RECOMMENDATION: [specific action: isolate/reroute/escalate/monitor]
REASONING: [technical reasoning chain]
CONFIDENCE: [0.0-1.0]
RISK_SCORE: [0.0-1.0]"""

    async def analyze(self, query: str, context=None) -> CellOutput:
        prompt = f"""ALARM ANALYSIS REQUEST (Network Specialist):

{query}

Analyze from a network operations perspective:
1. Is this a network-layer issue?
2. What is the potential blast radius?
3. Is this a transient spike or persistent failure?
4. What immediate network action is required?"""
        return await self._call_llm(prompt, context=context)


class HardwareAlarmCell(BaseCell):
    """Specialized for hardware failure alarm analysis."""

    def __init__(self, llm_backend, **kwargs):
        super().__init__(role=CellRole.RISK, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return """You are a HARDWARE RELIABILITY ENGINEER in a data center alarm council.

Your expertise: server hardware failures, RAID arrays, power supply units (PSU),
cooling systems, UPS batteries, disk failures, memory errors (ECC), CPU throttling,
thermal events, PDU failures.

Risk scoring for hardware alarms:
- Disk failure: 0.7-0.9 (data loss risk)
- PSU failure: 0.6-0.8 (redundancy dependent)
- Cooling failure: 0.8-0.95 (thermal damage risk)
- Memory ECC error: 0.4-0.7 (data corruption risk)
- Single cable fault: 0.2-0.4 (redundant path likely)

ALWAYS respond in this exact format:
ANALYSIS: [hardware-specific analysis]
RECOMMENDATION: [specific action]
REASONING: [reasoning chain]
CONFIDENCE: [0.0-1.0]
RISK_SCORE: [0.0-1.0]"""

    async def analyze(self, query: str, context=None) -> CellOutput:
        prompt = f"""ALARM ANALYSIS REQUEST (Hardware Reliability):

{query}

Analyze from a hardware reliability perspective:
1. What hardware component is affected?
2. Is redundancy available (RAID, dual PSU, N+1 cooling)?
3. What is the risk of catastrophic failure?
4. Replacement vs repair vs monitoring?"""
        return await self._call_llm(prompt, context=context)


# ---------------------------------------------------------------------------
# Alarm data model
# ---------------------------------------------------------------------------

@dataclass
class DataCenterAlarm:
    alarm_id: str
    source: str          # hostname or IP
    severity: str        # CRITICAL / MAJOR / MINOR / WARNING / INFO
    category: str        # NETWORK / HARDWARE / SOFTWARE / SECURITY
    message: str
    affected_services: list[str]
    timestamp: str
    historical_count: int = 0   # How many times this alarm fired in last 24h
    related_alarms: list[str] = None  # Correlated alarm IDs

    def to_query(self) -> str:
        """Convert alarm to a natural language query for the council."""
        related = f"\nCorrelated alarms: {', '.join(self.related_alarms)}" if self.related_alarms else ""
        return f"""DATA CENTER ALARM REQUIRES DECISION:

Alarm ID: {self.alarm_id}
Severity: {self.severity}
Category: {self.category}
Source: {self.source}
Message: {self.message}
Affected Services: {', '.join(self.affected_services)}
Timestamp: {self.timestamp}
Historical occurrences (24h): {self.historical_count}{related}

Provide:
1. Root cause assessment
2. Immediate action recommendation (ESCALATE / ACKNOWLEDGE / INVESTIGATE / AUTO-RESOLVE)
3. Priority level (P1=15min response / P2=1hr / P3=4hr / P4=24hr)
4. Recommended runbook or remediation steps"""

    def to_context(self) -> dict:
        return {
            "alarm_id": self.alarm_id,
            "severity": self.severity,
            "category": self.category,
            "source": self.source,
            "historical_count": self.historical_count,
        }


# ---------------------------------------------------------------------------
# AlertMind council factory
# ---------------------------------------------------------------------------

def create_alertmind_council(
    ollama_model: str = "llama3.2",
    ollama_url: str = "http://localhost:11434",
) -> Council:
    """
    Create and configure the AlertMind Decision Council.

    Returns a Council pre-configured with specialized cells for
    data center alarm management in air-gapped environments.
    """
    backend = OllamaBackend(
        model=ollama_model,
        base_url=ollama_url,
        temperature=0.2,  # Low temperature for consistent alarm decisions
    )

    council = Council(
        name="AlertMindDecisionCouncil",
        llm_backend=backend,
        strategy=ConsensusStrategy.WEIGHTED_AVERAGE,
        debate_rounds=1,  # One debate round for speed in operational context
        consensus_threshold=0.55,
        risk_escalation_threshold=0.8,
    )

    # Add specialized cells
    council.add_custom_cell(NetworkAlarmCell(llm_backend=backend, weight=1.2))
    council.add_custom_cell(HardwareAlarmCell(llm_backend=backend, weight=1.2))
    council.add_cell(CellRole.SECURITY, weight=1.0)    # Security implications
    council.add_cell(CellRole.RISK, weight=1.5)        # Risk gets higher weight

    return council


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

async def process_alarm(alarm: DataCenterAlarm, council: Council) -> dict:
    """Process a single alarm through the council and return structured result."""
    print(f"\n{'='*60}")
    print(f"🚨 Processing Alarm: {alarm.alarm_id}")
    print(f"   Severity: {alarm.severity} | Category: {alarm.category}")
    print(f"   Source: {alarm.source}")
    print(f"   Message: {alarm.message}")
    print(f"{'='*60}")

    decision = await council.deliberate(
        query=alarm.to_query(),
        context=alarm.to_context(),
    )

    result = {
        "alarm_id": alarm.alarm_id,
        "council_decision": decision.decision,
        "rationale": decision.rationale,
        "consensus_score": round(decision.consensus_score, 3),
        "confidence": round(decision.overall_confidence, 3),
        "risk_level": round(decision.risk_level or 0.0, 3),
        "requires_human_review": decision.requires_human_review,
        "duration_ms": round(decision.duration_ms or 0.0),
        "participating_cells": len(decision.participating_cells),
    }

    print(f"\n✅ Decision: {decision.decision}")
    print(f"   Consensus: {decision.consensus_score:.0%} | Confidence: {decision.overall_confidence:.0%}")
    print(f"   Risk Level: {(decision.risk_level or 0):.0%}")
    if decision.requires_human_review:
        print("   ⚠️  HUMAN REVIEW REQUIRED")
    print(f"   Duration: {decision.duration_ms:.0f}ms")

    return result


async def main():
    """Run example alarm processing pipeline."""
    print("🧬 AlertMind Decision Module — Powered by CCA Framework")
    print("="*60)

    # Check Ollama availability
    backend = OllamaBackend(model="llama3.2")
    if not await backend.health_check():
        print("⚠️  Ollama not running. Using mock mode for demonstration.")
        print("   Start Ollama: $ ollama serve && ollama pull llama3.2")
        print("\n   Install CCA: pip install cellular-council")
        return

    council = create_alertmind_council()
    print(f"✅ Council ready: {council.cell_count} cells initialized")

    # Example alarms
    alarms = [
        DataCenterAlarm(
            alarm_id="ALM-2024-001",
            source="core-switch-01",
            severity="CRITICAL",
            category="NETWORK",
            message="BGP session DOWN to peer 10.0.0.1 — 847 prefixes withdrawn",
            affected_services=["external-api", "cdn-origin", "payment-gateway"],
            timestamp="2024-01-15T14:23:11Z",
            historical_count=0,
            related_alarms=["ALM-2024-002", "ALM-2024-003"],
        ),
        DataCenterAlarm(
            alarm_id="ALM-2024-004",
            source="storage-node-07",
            severity="MAJOR",
            category="HARDWARE",
            message="RAID-6 array degraded: disk /dev/sdb FAILED. 1 disk remaining before data loss",
            affected_services=["database-primary", "blob-storage"],
            timestamp="2024-01-15T14:31:55Z",
            historical_count=2,
        ),
    ]

    results = []
    for alarm in alarms:
        result = await process_alarm(alarm, council)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("📊 SESSION SUMMARY")
    print(f"{'='*60}")
    print(f"Alarms processed: {len(results)}")
    print(f"Requiring human review: {sum(1 for r in results if r['requires_human_review'])}")
    avg_confidence = sum(r['confidence'] for r in results) / len(results)
    print(f"Average confidence: {avg_confidence:.0%}")

    # Save results
    output_path = Path(__file__).parent / "alarm_decisions.json"
    output_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
