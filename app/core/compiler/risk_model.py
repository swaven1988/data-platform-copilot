def compute_risk(
    shuffle_stages: int,
    executor_memory_gb: int,
    runtime_minutes: float
):
    risk_score = 0
    factors = []

    if shuffle_stages > 2:
        risk_score += 25
        factors.append("High shuffle amplification")

    if executor_memory_gb < 8:
        risk_score += 20
        factors.append("Low executor memory")

    if runtime_minutes > 60:
        risk_score += 20
        factors.append("Long runtime risk")

    failure_probability = round(min(0.9, risk_score / 100), 2)

    if risk_score < 30:
        level = "LOW"
    elif risk_score < 70:
        level = "MEDIUM"
    else:
        level = "HIGH"

    confidence = round(1 - (risk_score / 150), 2)

    return {
        "risk_score": risk_score,
        "risk_level": level,
        "failure_probability": failure_probability,
        "confidence_score": max(0.5, confidence),
        "factors": factors
    }