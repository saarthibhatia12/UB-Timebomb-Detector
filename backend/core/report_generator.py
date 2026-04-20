"""
report_generator.py - Source-level report generator (Deliverable 4).

Generates JSON and plain-text reports from classified findings.
"""

from typing import Any, Dict, List, Optional


SEVERITY_ICON = {
    "critical": "CRIT",
    "high": "HIGH",
    "medium": "MED",
    "low": "LOW",
    "info": "INFO",
}

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _read_source_lines(source_path: str) -> List[str]:
    """Read source file into a list of lines."""
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def _calc_risk_score(findings: List[Dict[str, Any]]) -> int:
    """Calculate an overall risk score from 0 to 100."""
    if not findings:
        return 0

    severity_weights = {
        "critical": 30,
        "high": 20,
        "medium": 10,
        "low": 5,
        "info": 0,
    }
    total = sum(severity_weights.get(f["severity"], 0) for f in findings)
    return min(100, total)


def generate_report(
    findings: List[Dict[str, Any]],
    source_path: str,
    compiled_result: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Generate a full report object for JSON serialization and UI/CLI usage.
    """
    source_lines = _read_source_lines(source_path)

    sorted_findings = sorted(
        findings,
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", ""), 99),
    )

    enriched: List[Dict[str, Any]] = []
    for finding in sorted_findings:
        loc = finding.get("location")
        snippet = ""

        if loc and loc.get("line") and source_lines:
            line_num = int(loc["line"])
            start = max(0, line_num - 2)
            end = min(len(source_lines), line_num + 2)

            snippet_lines: List[str] = []
            for i in range(start, end):
                marker = ">>>" if i == line_num - 1 else "   "
                snippet_lines.append(f"{marker} {i + 1:>4} | {source_lines[i].rstrip()}")

            snippet = "\n".join(snippet_lines)

        enriched.append(
            {
                **finding,
                "source_snippet": snippet,
                "severity_icon": SEVERITY_ICON.get(finding.get("severity", ""), ""),
            }
        )

    risk_score = _calc_risk_score(findings)

    category_counts: Dict[str, int] = {}
    for finding in findings:
        category = finding.get("category", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    report = {
        "source_file": source_path,
        "source_lines": [line.rstrip() for line in source_lines],
        "total_findings": len(findings),
        "risk_score": risk_score,
        "risk_level": (
            "CRITICAL"
            if risk_score >= 70
            else "HIGH"
            if risk_score >= 40
            else "MEDIUM"
            if risk_score >= 20
            else "LOW"
        ),
        "category_counts": category_counts,
        "findings": enriched,
        "functions_analyzed": len(compiled_result["functions"]) if compiled_result else 0,
        "functions_inlined": len(compiled_result.get("o0_only", [])) if compiled_result else 0,
    }

    return report


def report_to_text(report: Dict[str, Any]) -> str:
    """Convert a report dict into human-readable plain text."""
    lines: List[str] = []

    lines.append("=" * 60)
    lines.append("  UB TIME BOMB DETECTOR - ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append(f"  File: {report['source_file']}")
    lines.append(f"  Risk Score: {report['risk_score']}/100 ({report['risk_level']})")
    lines.append(f"  Functions Analyzed: {report['functions_analyzed']}")
    lines.append(f"  Time Bombs Found: {report['total_findings']}")
    lines.append("=" * 60)

    for idx, finding in enumerate(report.get("findings", []), start=1):
        lines.append("")
        icon = finding.get("severity_icon", "")
        lines.append(f"[{icon} {finding['severity'].upper()}] #{idx} - {finding['readable_name']}")
        lines.append(f"  Category  : {finding['category']}")
        lines.append(f"  Confidence: {finding['confidence']}")

        if finding.get("location"):
            loc = finding["location"]
            lines.append(f"  Location  : {loc.get('file', '?')}:{loc.get('line', '?')}")

        lines.append(f"  Detail    : {finding['detail']}")
        lines.append(f"  Fix       : {finding['fix']}")

        if finding.get("source_snippet"):
            lines.append("  Code:")
            for snippet_line in finding["source_snippet"].split("\n"):
                lines.append(f"    {snippet_line}")

        if finding.get("metrics"):
            metrics = finding["metrics"]
            lines.append(
                f"  Blocks    : O0={metrics['blocks_O0']}  O2={metrics['blocks_O2']}"
            )
            lines.append(
                f"  Branches  : O0={metrics['branches_O0']}  O2={metrics['branches_O2']}"
            )

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
