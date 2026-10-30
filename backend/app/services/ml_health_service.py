import os
import logging
import joblib
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.schemas.machine_health import RiskLevel, MLHealthPrediction

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "cycle_deviation_pct",
    "rate_efficiency_pct",
    "failures_24h",
    "failures_7d",
    "downtime_pct",
    "unresolved_warnings",
    "operating_hours",
    "days_since_maint",
    "incident_count"
]

FEATURE_LABELS = {
    "cycle_deviation_pct": "Cycle Time Elongation",
    "rate_efficiency_pct": "Processing Rate Efficiency Loss",
    "failures_24h": "Active Failures (24h)",
    "failures_7d": "Active Failures (7d)",
    "downtime_pct": "Unplanned Downtime Ratio",
    "unresolved_warnings": "Unresolved Operator Warnings",
    "operating_hours": "Cumulative Run Time",
    "days_since_maint": "Days Since Maintenance",
    "incident_count": "Historical Incident Frequency"
}

RISK_LEVEL_MAP = {
    0: RiskLevel.LOW,
    1: RiskLevel.MEDIUM,
    2: RiskLevel.HIGH,
    3: RiskLevel.CRITICAL
}

RISK_LEVEL_REV_MAP = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3
}

class MachineHealthMLService:
    """
    Industrial Machine Learning Service for Equipment Health & Failure Risk Prediction.
    Employs an ensemble of Random Forest Classifier (categorical risk level & failure probability)
    and Random Forest Regressor (continuous health score 0-100), with feature importance ranking.
    """

    _classifier: Optional[RandomForestClassifier] = None
    _regressor: Optional[RandomForestRegressor] = None
    _model_path: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml_models", "machine_health_rf.joblib")
    _last_trained_at: Optional[datetime] = None
    _trained_samples_count: int = 0
    _feature_importances: Dict[str, float] = {}

    @classmethod
    def _generate_synthetic_training_dataset(cls, n_samples: int = 600) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Synthesizes a realistic, domain-grounded industrial dataset modeling CNC milling,
        laser cutting, and welding degradation curves with realistic manufacturing variance.
        """
        np.random.seed(42)
        X = []
        y_risk = []
        y_health = []

        samples_per_class = n_samples // 4

        # 1. Healthy / Calibrated Machines (Class 0: LOW Risk, Health 85-100)
        for _ in range(samples_per_class):
            cycle_dev = np.random.uniform(-5.0, 8.0)
            rate_eff = np.random.uniform(92.0, 108.0)
            f_24h = 0
            f_7d = 0
            downtime = np.random.uniform(0.0, 3.5)
            warnings = 0 if np.random.rand() > 0.15 else 1
            op_hours = np.random.uniform(5.0, 400.0)
            days_maint = np.random.uniform(1.0, 25.0)
            incidents = np.random.choice([0, 1], p=[0.85, 0.15])

            health = np.clip(100.0 - (max(0, cycle_dev) * 0.4 + downtime * 0.8 + warnings * 3.0 + np.random.normal(0, 1.5)), 85.0, 100.0)

            X.append([cycle_dev, rate_eff, f_24h, f_7d, downtime, warnings, op_hours, days_maint, incidents])
            y_risk.append(0)  # LOW
            y_health.append(health)

        # 2. Moderate Wear / Attention Warranted (Class 1: MEDIUM Risk, Health 70-84)
        for _ in range(samples_per_class):
            cycle_dev = np.random.uniform(10.0, 24.0)
            rate_eff = np.random.uniform(80.0, 92.0)
            f_24h = 0
            f_7d = 0 if np.random.rand() > 0.3 else 1
            downtime = np.random.uniform(4.0, 9.0)
            warnings = np.random.choice([0, 1, 2], p=[0.3, 0.5, 0.2])
            op_hours = np.random.uniform(200.0, 800.0)
            days_maint = np.random.uniform(20.0, 60.0)
            incidents = np.random.choice([1, 2, 3], p=[0.5, 0.35, 0.15])

            health = np.clip(84.0 - ((cycle_dev - 10.0) * 0.7 + downtime * 0.6 + f_7d * 5.0 + warnings * 2.5 + np.random.normal(0, 1.5)), 70.0, 84.0)

            X.append([cycle_dev, rate_eff, f_24h, f_7d, downtime, warnings, op_hours, days_maint, incidents])
            y_risk.append(1)  # MEDIUM
            y_health.append(health)

        # 3. High Degradation / Impending Component Failure (Class 2: HIGH Risk, Health 50-69)
        for _ in range(samples_per_class):
            cycle_dev = np.random.uniform(25.0, 48.0)
            rate_eff = np.random.uniform(65.0, 80.0)
            f_24h = 1 if np.random.rand() > 0.6 else 0
            f_7d = np.random.choice([1, 2], p=[0.6, 0.4])
            downtime = np.random.uniform(9.0, 18.0)
            warnings = np.random.choice([1, 2, 3], p=[0.3, 0.5, 0.2])
            op_hours = np.random.uniform(400.0, 1500.0)
            days_maint = np.random.uniform(45.0, 90.0)
            incidents = np.random.choice([2, 3, 4, 5], p=[0.2, 0.4, 0.3, 0.1])

            health = np.clip(69.0 - ((cycle_dev - 25.0) * 0.6 + downtime * 0.5 + f_7d * 4.0 + f_24h * 5.0 + np.random.normal(0, 1.5)), 50.0, 69.0)

            X.append([cycle_dev, rate_eff, f_24h, f_7d, downtime, warnings, op_hours, days_maint, incidents])
            y_risk.append(2)  # HIGH
            y_health.append(health)

        # 4. Critical Mechanical / Thermal Breakdown (Class 3: CRITICAL Risk, Health 0-49)
        for _ in range(samples_per_class):
            cycle_dev = np.random.uniform(50.0, 90.0)
            rate_eff = np.random.uniform(40.0, 65.0)
            f_24h = np.random.choice([1, 2, 3], p=[0.4, 0.4, 0.2])
            f_7d = np.random.choice([2, 3, 4], p=[0.4, 0.4, 0.2])
            downtime = np.random.uniform(18.0, 40.0)
            warnings = np.random.choice([2, 3, 4], p=[0.3, 0.4, 0.3])
            op_hours = np.random.uniform(600.0, 2500.0)
            days_maint = np.random.uniform(60.0, 150.0)
            incidents = np.random.choice([4, 5, 6, 8], p=[0.3, 0.3, 0.2, 0.2])

            health = np.clip(49.0 - ((cycle_dev - 50.0) * 0.5 + downtime * 0.4 + f_7d * 3.0 + f_24h * 4.0 + np.random.normal(0, 2.0)), 10.0, 49.0)

            X.append([cycle_dev, rate_eff, f_24h, f_7d, downtime, warnings, op_hours, days_maint, incidents])
            y_risk.append(3)  # CRITICAL
            y_health.append(health)

        return np.array(X, dtype=np.float32), np.array(y_risk, dtype=np.int32), np.array(y_health, dtype=np.float32)

    @classmethod
    def train_models(cls, custom_data: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None) -> Dict[str, Any]:
        """
        Fits both the Random Forest Classifier and Regressor and persists weights to disk.
        """
        if custom_data:
            X, y_risk, y_health = custom_data
        else:
            X, y_risk, y_health = cls._generate_synthetic_training_dataset(n_samples=600)

        # 1. Random Forest Classifier for Risk Level & Failure Probability
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        clf.fit(X, y_risk)

        # 2. Random Forest Regressor for Continuous Health Score
        reg = RandomForestRegressor(
            n_estimators=100,
            max_depth=6,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        reg.fit(X, y_health)

        cls._classifier = clf
        cls._regressor = reg
        cls._last_trained_at = datetime.utcnow()
        cls._trained_samples_count = len(X)

        # Compute normalized feature importances
        raw_importances = (clf.feature_importances_ + reg.feature_importances_) / 2.0
        cls._feature_importances = {
            FEATURE_NAMES[i]: round(float(raw_importances[i]), 4)
            for i in range(len(FEATURE_NAMES))
        }

        # Persist to disk
        try:
            os.makedirs(os.path.dirname(cls._model_path), exist_ok=True)
            payload = {
                "classifier": clf,
                "regressor": reg,
                "last_trained_at": cls._last_trained_at,
                "trained_samples_count": cls._trained_samples_count,
                "feature_importances": cls._feature_importances,
                "feature_names": FEATURE_NAMES
            }
            joblib.dump(payload, cls._model_path)
            logger.info(f"MachineHealthMLService models persisted successfully to {cls._model_path}")
        except Exception as e:
            logger.warning(f"Could not persist ML models to disk: {e}")

        return {
            "status": "TRAINED",
            "samples": len(X),
            "featureImportances": cls._feature_importances,
            "trainedAt": cls._last_trained_at.isoformat()
        }

    @classmethod
    def ensure_models_loaded(cls):
        """
        Loads pre-trained models from disk, or triggers training if not yet serialized.
        """
        if cls._classifier is not None and cls._regressor is not None:
            return

        if os.path.exists(cls._model_path):
            try:
                payload = joblib.load(cls._model_path)
                cls._classifier = payload.get("classifier")
                cls._regressor = payload.get("regressor")
                cls._last_trained_at = payload.get("last_trained_at")
                cls._trained_samples_count = payload.get("trained_samples_count", 600)
                cls._feature_importances = payload.get("feature_importances", {})
                logger.info("MachineHealthMLService models loaded successfully from disk.")
                return
            except Exception as e:
                logger.warning(f"Could not load ML models from {cls._model_path}: {e}. Retraining...")

        # If file missing or corrupted, train fresh models
        logger.info("Initializing and training Random Forest models for Machine Health Service...")
        cls.train_models()

    @classmethod
    def predict(
        cls,
        cycle_deviation_pct: float,
        rate_efficiency_pct: float,
        failures_24h: int,
        failures_7d: int,
        downtime_pct: float,
        unresolved_warnings: int,
        total_operating_seconds: float,
        days_since_maint: Optional[float] = None,
        incident_count: int = 0
    ) -> MLHealthPrediction:
        """
        Executes real-time inference on operational telemetry using trained Random Forest models.
        """
        cls.ensure_models_loaded()

        op_hours = round(max(0.0, total_operating_seconds) / 3600.0, 2)
        days_maint = float(days_since_maint if days_since_maint is not None else 30.0)

        feature_vector = np.array([[
            float(cycle_deviation_pct),
            float(rate_efficiency_pct),
            float(failures_24h),
            float(failures_7d),
            float(downtime_pct),
            float(unresolved_warnings),
            float(op_hours),
            days_maint,
            float(incident_count)
        ]], dtype=np.float32)

        # 1. Classification Inference
        pred_class_idx = int(cls._classifier.predict(feature_vector)[0])
        pred_risk_level = RISK_LEVEL_MAP.get(pred_class_idx, RiskLevel.MEDIUM)

        # Failure probability (probability of HIGH or CRITICAL risk)
        probs = cls._classifier.predict_proba(feature_vector)[0]
        # Sum probability of class 2 (HIGH) and class 3 (CRITICAL)
        high_critical_prob = float(sum(probs[i] for i in range(len(probs)) if i >= 2))
        failure_prob = round(min(1.0, max(0.0, high_critical_prob)), 3)

        # 2. Regression Inference (Health Score 0-100)
        raw_score = float(cls._regressor.predict(feature_vector)[0])
        pred_health_score = int(round(np.clip(raw_score, 0.0, 100.0)))

        # 3. Explainability: Identify Primary Risk Driver
        primary_driver = cls._determine_primary_risk_driver(
            cycle_deviation_pct=cycle_deviation_pct,
            rate_efficiency_pct=rate_efficiency_pct,
            failures_24h=failures_24h,
            failures_7d=failures_7d,
            downtime_pct=downtime_pct,
            unresolved_warnings=unresolved_warnings,
            days_since_maint=days_maint
        )

        return MLHealthPrediction(
            modelType="RandomForestClassifier (n=100) + Regressor (n=100)",
            predictedRiskLevel=pred_risk_level,
            predictedHealthScore=pred_health_score,
            failureProbability=failure_prob,
            featureImportances=cls._feature_importances,
            primaryRiskDriver=primary_driver,
            modelConfidence=round(float(np.max(probs)), 2),
            trainedSamplesCount=cls._trained_samples_count,
            evaluatedAt=datetime.utcnow()
        )

    @classmethod
    def _determine_primary_risk_driver(
        cls,
        cycle_deviation_pct: float,
        rate_efficiency_pct: float,
        failures_24h: int,
        failures_7d: int,
        downtime_pct: float,
        unresolved_warnings: int,
        days_since_maint: float
    ) -> str:
        """
        Identifies the dominant contributing signal for human operators.
        """
        candidates = []
        if cycle_deviation_pct > 15.0:
            candidates.append((cycle_deviation_pct * 1.5, f"Cycle Time Elongation (+{cycle_deviation_pct:.1f}%)"))
        if failures_24h > 0:
            candidates.append((failures_24h * 30.0, f"{failures_24h} Failure(s) in Last 24 Hours"))
        if failures_7d > 1:
            candidates.append((failures_7d * 20.0, f"{failures_7d} Failures in Last 7 Days"))
        if downtime_pct > 10.0:
            candidates.append((downtime_pct * 1.8, f"High Downtime Ratio ({downtime_pct:.1f}%)"))
        if unresolved_warnings > 0:
            candidates.append((unresolved_warnings * 12.0, f"{unresolved_warnings} Unresolved Warning(s)"))
        if rate_efficiency_pct < 85.0:
            candidates.append(((100.0 - rate_efficiency_pct) * 1.2, f"Rate Efficiency Deficit ({rate_efficiency_pct:.1f}%)"))
        if days_since_maint > 90.0:
            candidates.append((days_since_maint * 0.2, f"Overdue Maintenance ({days_since_maint:.0f}d since service)"))

        if not candidates:
            return "All telemetry indicators operating within nominal thresholds"

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    @classmethod
    def get_model_metadata(cls) -> Dict[str, Any]:
        """
        Returns model diagnostics and feature importances for UI / admin inspection.
        """
        cls.ensure_models_loaded()
        return {
            "algorithm": "Random Forest (scikit-learn)",
            "classificationTrees": 100,
            "regressionTrees": 100,
            "features": [
                {"name": name, "label": FEATURE_LABELS[name], "importance": cls._feature_importances.get(name, 0.0)}
                for name in FEATURE_NAMES
            ],
            "trainedSamples": cls._trained_samples_count,
            "lastTrainedAt": cls._last_trained_at.isoformat() if cls._last_trained_at else None,
            "targetClasses": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "targetMetric": "Machine Health Score (0-100)"
        }
