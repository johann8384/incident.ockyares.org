#!/usr/bin/env python3
"""Generate security scan summary report"""

import json
import os
from datetime import datetime

def load_json_report(filename):
    """Load JSON report if it exists"""
    filepath = f"security-reports/{filename}"
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def generate_summary():
    """Generate security summary report"""
    
    summary = {
        'scan_date': datetime.now().isoformat(),
        'reports': {},
        'totals': {
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
    }
    
    # Bandit report
    bandit = load_json_report('bandit-report.json')
    if bandit:
        summary['reports']['bandit'] = {
            'total_issues': len(bandit.get('results', [])),
            'high_severity': len([r for r in bandit.get('results', []) if r.get('issue_severity') == 'HIGH']),
            'medium_severity': len([r for r in bandit.get('results', []) if r.get('issue_severity') == 'MEDIUM']),
            'low_severity': len([r for r in bandit.get('results', []) if r.get('issue_severity') == 'LOW'])
        }
    
    # Safety report
    safety = load_json_report('safety-report.json')
    if safety:
        vulnerabilities = safety.get('vulnerabilities', [])
        summary['reports']['safety'] = {
            'total_vulnerabilities': len(vulnerabilities),
            'details': vulnerabilities
        }
    
    # Trivy report
    trivy = load_json_report('trivy-report.json')
    if trivy:
        results = trivy.get('Results', [])
        total_vulns = 0
        severities = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'UNKNOWN': 0}
        
        for result in results:
            vulns = result.get('Vulnerabilities', [])
            total_vulns += len(vulns)
            for vuln in vulns:
                severity = vuln.get('Severity', 'UNKNOWN')
                severities[severity] = severities.get(severity, 0) + 1
        
        summary['reports']['trivy'] = {
            'total_vulnerabilities': total_vulns,
            'severities': severities
        }
    
    # Write summary
    with open('security-reports/summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n🔒 SECURITY SCAN SUMMARY")
    print("=" * 50)
    print(f"Scan Date: {summary['scan_date']}")
    
    for tool, data in summary['reports'].items():
        print(f"\n{tool.upper()}:")
        if tool == 'bandit':
            print(f"  Total Issues: {data['total_issues']}")
            print(f"  High: {data['high_severity']}, Medium: {data['medium_severity']}, Low: {data['low_severity']}")
        elif tool == 'safety':
            print(f"  Total Vulnerabilities: {data['total_vulnerabilities']}")
        elif tool == 'trivy':
            print(f"  Total Vulnerabilities: {data['total_vulnerabilities']}")
            print(f"  High: {data['severities']['HIGH']}, Medium: {data['severities']['MEDIUM']}, Low: {data['severities']['LOW']}")
    
    print("\n📁 Detailed reports available in security-reports/ directory")

if __name__ == "__main__":
    generate_summary()
