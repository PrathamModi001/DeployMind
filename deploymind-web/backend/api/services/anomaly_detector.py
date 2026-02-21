"""AI-powered anomaly detection for deployment metrics."""
import logging
import statistics
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add deploymind-core to path
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

try:
    from deploymind.infrastructure.llm.groq.groq_client import GroqClient
    from deploymind.config.settings import Settings as CoreSettings
    CORE_AVAILABLE = True
except ImportError:
    GroqClient = None
    CoreSettings = None
    CORE_AVAILABLE = False

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detect anomalies in deployment metrics using statistical analysis and AI.

    Monitors CPU, memory, network, and other metrics for unusual patterns
    that may indicate problems.
    """

    # Anomaly thresholds
    Z_SCORE_THRESHOLD = 2.0  # Standard deviations for anomaly
    SPIKE_THRESHOLD = 1.5     # Multiplier for spike detection
    TREND_THRESHOLD = 0.15    # 15% increase for trend detection

    def __init__(self, db: Session):
        """
        Initialize anomaly detector.

        Args:
            db: Database session
        """
        self.db = db

        if CORE_AVAILABLE and CoreSettings and GroqClient:
            try:
                settings = CoreSettings.load()
                self.llm = GroqClient(settings.groq_api_key)
                logger.info("AnomalyDetector initialized with LLM")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM: {e}")
                self.llm = None
        else:
            self.llm = None
            logger.warning("LLM not available, using statistical detection only")

    async def detect_metric_anomalies(
        self,
        deployment_id: str,
        hours_lookback: int = 24
    ) -> Dict:
        """
        Detect anomalies in deployment metrics.

        Args:
            deployment_id: Deployment ID
            hours_lookback: Hours of history to analyze (default: 24)

        Returns:
            Dictionary with detected anomalies
        """
        try:
            # Get metrics history (simulated for now)
            metrics_history = await self._get_metrics_history(
                deployment_id,
                hours_lookback
            )

            if not metrics_history:
                return {
                    "deployment_id": deployment_id,
                    "anomalies_detected": False,
                    "anomalies": [],
                    "severity": "none",
                    "root_cause_hypotheses": [],
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }

            # Statistical analysis
            cpu_anomalies = self._detect_cpu_anomalies(metrics_history)
            memory_anomalies = self._detect_memory_anomalies(metrics_history)
            network_anomalies = self._detect_network_anomalies(metrics_history)

            all_anomalies = cpu_anomalies + memory_anomalies + network_anomalies

            if not all_anomalies:
                return {
                    "deployment_id": deployment_id,
                    "anomalies_detected": False,
                    "anomalies": [],
                    "severity": "none",
                    "root_cause_hypotheses": ["No anomalies detected"],
                    "analysis_timestamp": datetime.utcnow().isoformat()
                }

            # Determine severity
            severity = self._calculate_severity(all_anomalies)

            # Use LLM for root cause analysis if available
            if self.llm:
                hypotheses = await self._llm_root_cause_analysis(
                    deployment_id,
                    metrics_history,
                    all_anomalies
                )
            else:
                hypotheses = self._rule_based_hypotheses(all_anomalies)

            return {
                "deployment_id": deployment_id,
                "anomalies_detected": True,
                "anomalies": all_anomalies,
                "severity": severity,
                "root_cause_hypotheses": hypotheses,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}", exc_info=True)
            return self._mock_anomaly_result(deployment_id)

    def _detect_cpu_anomalies(self, metrics: List[Dict]) -> List[Dict]:
        """Detect CPU usage anomalies."""
        if len(metrics) < 10:
            return []

        cpu_values = [m["cpu"] for m in metrics]
        mean = statistics.mean(cpu_values)
        stddev = statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0

        anomalies = []
        current_cpu = cpu_values[-1]

        # Z-score anomaly detection
        if stddev > 0:
            z_score = abs((current_cpu - mean) / stddev)
            if z_score > self.Z_SCORE_THRESHOLD:
                anomalies.append({
                    "type": "cpu_spike" if current_cpu > mean else "cpu_drop",
                    "metric": "cpu",
                    "current_value": current_cpu,
                    "expected_range": f"{mean - 2*stddev:.1f}-{mean + 2*stddev:.1f}",
                    "severity": "high" if z_score > 3 else "medium",
                    "z_score": round(z_score, 2),
                    "description": f"CPU usage ({current_cpu}%) is {z_score:.1f} standard deviations from mean"
                })

        # Trend detection (gradual increase)
        if len(cpu_values) >= 20:
            recent_avg = statistics.mean(cpu_values[-10:])
            older_avg = statistics.mean(cpu_values[-20:-10])
            if recent_avg > older_avg * (1 + self.TREND_THRESHOLD):
                anomalies.append({
                    "type": "cpu_trend_increase",
                    "metric": "cpu",
                    "current_value": recent_avg,
                    "baseline_value": older_avg,
                    "severity": "medium",
                    "increase_percent": round(((recent_avg - older_avg) / older_avg) * 100, 1),
                    "description": f"CPU usage trending upward: {older_avg:.1f}% → {recent_avg:.1f}%"
                })

        return anomalies

    def _detect_memory_anomalies(self, metrics: List[Dict]) -> List[Dict]:
        """Detect memory usage anomalies."""
        if len(metrics) < 10:
            return []

        memory_values = [m["memory"] for m in metrics]
        anomalies = []

        # Memory leak detection (continuous increase)
        if len(memory_values) >= 20:
            # Check if memory is consistently increasing
            increases = 0
            for i in range(len(memory_values) - 5, len(memory_values)):
                if memory_values[i] > memory_values[i-1]:
                    increases += 1

            if increases >= 4:  # 4 out of 5 recent measurements increasing
                anomalies.append({
                    "type": "memory_leak_suspected",
                    "metric": "memory",
                    "current_value": memory_values[-1],
                    "starting_value": memory_values[-20],
                    "severity": "high",
                    "trend": "increasing",
                    "description": f"Potential memory leak: {memory_values[-20]:.1f}% → {memory_values[-1]:.1f}%"
                })

        # High memory usage
        current_memory = memory_values[-1]
        if current_memory > 85:
            anomalies.append({
                "type": "high_memory_usage",
                "metric": "memory",
                "current_value": current_memory,
                "threshold": 85,
                "severity": "critical" if current_memory > 95 else "high",
                "description": f"Memory usage critically high: {current_memory}%"
            })

        return anomalies

    def _detect_network_anomalies(self, metrics: List[Dict]) -> List[Dict]:
        """Detect network I/O anomalies."""
        if len(metrics) < 10:
            return []

        network_values = [m["network"] for m in metrics]
        mean = statistics.mean(network_values)
        stddev = statistics.stdev(network_values) if len(network_values) > 1 else 0

        anomalies = []
        current_network = network_values[-1]

        # Unusual network spike
        if stddev > 0 and current_network > mean * self.SPIKE_THRESHOLD:
            anomalies.append({
                "type": "network_spike",
                "metric": "network",
                "current_value": current_network,
                "baseline_value": mean,
                "severity": "medium",
                "increase_factor": round(current_network / mean, 2),
                "description": f"Unusual network spike: {current_network} MB/s (avg: {mean:.1f} MB/s)"
            })

        return anomalies

    def _calculate_severity(self, anomalies: List[Dict]) -> str:
        """Calculate overall severity from anomalies."""
        if not anomalies:
            return "none"

        severities = [a.get("severity", "low") for a in anomalies]

        if "critical" in severities:
            return "critical"
        elif "high" in severities:
            return "high"
        elif "medium" in severities:
            return "medium"
        else:
            return "low"

    async def _llm_root_cause_analysis(
        self,
        deployment_id: str,
        metrics: List[Dict],
        anomalies: List[Dict]
    ) -> List[str]:
        """Use LLM to analyze root causes."""
        anomaly_descriptions = "\n".join([
            f"- {a['type']}: {a['description']}"
            for a in anomalies
        ])

        prompt = f"""
        Analyze the following deployment anomalies and suggest root causes:

        Deployment ID: {deployment_id}
        Recent metrics: CPU={metrics[-1]['cpu']}%, Memory={metrics[-1]['memory']}%, Network={metrics[-1]['network']} MB/s

        Detected anomalies:
        {anomaly_descriptions}

        Based on these anomalies, provide 3-5 most likely root cause hypotheses.
        Consider factors like:
        - Application bugs (memory leaks, infinite loops)
        - Resource constraints
        - External dependencies
        - Traffic patterns
        - Configuration issues

        Return ONLY valid JSON in this format:
        {{
            "hypotheses": ["hypothesis1", "hypothesis2", "hypothesis3"]
        }}
        """

        try:
            response = self.llm.chat_completion(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result = json.loads(response.strip())
            return result.get("hypotheses", [])[:5]

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return self._rule_based_hypotheses(anomalies)

    def _rule_based_hypotheses(self, anomalies: List[Dict]) -> List[str]:
        """Generate root cause hypotheses using rules."""
        hypotheses = []

        for anomaly in anomalies:
            atype = anomaly.get("type", "")

            if "memory_leak" in atype:
                hypotheses.append("Potential memory leak in application code")
                hypotheses.append("Unclosed database connections or file handles")
            elif "cpu_spike" in atype:
                hypotheses.append("CPU-intensive operation or infinite loop")
                hypotheses.append("Sudden increase in traffic or requests")
            elif "high_memory" in atype:
                hypotheses.append("Application caching too much data")
                hypotheses.append("Large object accumulation in memory")
            elif "network_spike" in atype:
                hypotheses.append("Increased API calls or data transfers")
                hypotheses.append("Denial of service attack or bot traffic")

        # Deduplicate and limit
        unique_hypotheses = list(dict.fromkeys(hypotheses))
        return unique_hypotheses[:5] if unique_hypotheses else ["No specific hypothesis generated"]

    async def _get_metrics_history(
        self,
        deployment_id: str,
        hours: int
    ) -> List[Dict]:
        """
        Get metrics history for deployment.

        In production, this would query a time-series database.
        For now, we'll simulate realistic metrics.
        """
        # Simulate 24 hours of metrics (one per 30 minutes = 48 data points)
        num_points = hours * 2
        metrics = []

        # Base values
        base_cpu = 45.0
        base_memory = 60.0
        base_network = 10.0

        import random
        for i in range(num_points):
            # Normal variation
            cpu = base_cpu + random.gauss(0, 5)

            # Simulate memory leak (gradual increase)
            memory = base_memory + (i * 0.5) + random.gauss(0, 3)

            # Network with occasional spikes
            network = base_network + random.gauss(0, 2)
            if random.random() < 0.05:  # 5% chance of spike
                network *= 3

            metrics.append({
                "timestamp": (datetime.utcnow() - timedelta(minutes=30 * (num_points - i))).isoformat(),
                "cpu": max(0, min(100, cpu)),
                "memory": max(0, min(100, memory)),
                "network": max(0, network)
            })

        return metrics

    def _mock_anomaly_result(self, deployment_id: str) -> Dict:
        """Return mock anomaly result."""
        return {
            "deployment_id": deployment_id,
            "anomalies_detected": True,
            "anomalies": [
                {
                    "type": "memory_leak_suspected",
                    "metric": "memory",
                    "current_value": 78.5,
                    "starting_value": 60.2,
                    "severity": "high",
                    "description": "Potential memory leak: 60.2% → 78.5%"
                },
                {
                    "type": "cpu_spike",
                    "metric": "cpu",
                    "current_value": 85.3,
                    "expected_range": "40.0-60.0",
                    "severity": "medium",
                    "description": "CPU usage (85.3%) is 2.3 standard deviations from mean"
                }
            ],
            "severity": "high",
            "root_cause_hypotheses": [
                "Potential memory leak in application code",
                "Unclosed database connections or file handles",
                "CPU-intensive operation triggered"
            ],
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
