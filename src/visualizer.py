"""
visualizer.py
Helper rendering utilities.
"""

def render_overview_metrics(profile: dict) -> dict:
    """Return display-ready values from a profile dict."""
    score = profile["quality_score"]
    return {
        "score": score,
        "score_label": "Good" if score >= 80 else "Needs Work" if score >= 60 else "Poor",
        "score_color": "#22c55e" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444",
        "total_missing": profile["total_missing"],
        "duplicates": profile["duplicate_rows"],
        "issue_count": len(profile["issues"]),
        "dimension_scores": profile.get("dimension_scores", {}),
    }
