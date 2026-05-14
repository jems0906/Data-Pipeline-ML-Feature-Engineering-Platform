# Incident Report Template

Use this template for production incidents and postmortems.

## 1. Incident Summary
- Incident ID:
- Title:
- Severity (SEV-1/2/3/4):
- Status (Open/Monitoring/Resolved):
- Reported by:
- Incident commander:
- Start time (UTC):
- End time (UTC):
- Duration:

## 2. Impact Assessment
- User impact:
- Business impact:
- Affected services:
- Affected environments:
- Data impact (loss/corruption/latency):

## 3. Detection and Alerting
- Detection method (automated/manual):
- First alert source:
- Alert payload / ID:
- Time to detect (TTD):

## 4. Timeline (UTC)
| Time | Event | Owner |
|---|---|---|
| HH:MM | Incident detected | Name |
| HH:MM | Mitigation started | Name |
| HH:MM | Service restored | Name |

## 5. Root Cause Analysis
- Trigger event:
- Primary root cause:
- Contributing factors:
- Why existing safeguards did not prevent incident:

## 6. Mitigation and Recovery
- Immediate mitigation steps:
- Recovery actions completed:
- Rollback used (Yes/No, details):
- Time to recover (TTR):

## 7. Corrective and Preventive Actions (CAPA)
| Action | Owner | Due Date | Status |
|---|---|---|---|
| Example: Add retry with backoff to dispatch transport | Team A | YYYY-MM-DD | Open |

## 8. Validation and Closure
- Validation checks performed:
- Monitoring window after fix:
- Closure approval:
- Lessons learned:

## 9. Communications
- Internal updates sent:
- External/customer updates sent:
- Final stakeholder summary link:
