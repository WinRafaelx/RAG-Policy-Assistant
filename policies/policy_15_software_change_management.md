# Software Change Management Policy

**Policy ID:** TTB-TECH-001  
**Effective Date:** January 1, 2025  
**Owner Department:** Technology Risk  

## 1. Scope and Change Classifications
This policy defines the governance and approvals required for deploying changes to production systems at ttb Policy Assistant Demo Bank. Changes are categorized into three classes:
* **Standard Change:** Low-risk, repetitive changes with pre-approved procedures (e.g., routine patch installations).
* **Normal Change:** Medium- to high-risk modifications to systems, networks, or applications that require formal review.
* **Emergency Change:** Urgent updates required to restore service or patch a critical active security vulnerability.

## 2. Standard Change Guidelines
* **Pre-Approval:** Standard changes must use procedures that have been validated and pre-approved by the Change Advisory Board (CAB).
* **Logging Timeline:** Although pre-approved, standard changes must be logged in the change management system at least 24 hours prior to deployment.

## 3. Normal Change Procedures and CAB Schedule
* **CAB Review:** All normal changes must undergo a formal review and approval process by the CAB.
* **CAB Meeting:** The CAB meets weekly every Wednesday at 10:00 AM local time.
* **Submission Lead Time:** Normal change requests must be submitted in the system at least 5 business days prior to the CAB meeting. Late submissions will be deferred to the following week.
* **Testing Requirement:** Change requests must include documented test results in the staging environment.

## 4. Emergency Change Governance
* **Emergency Definition:** A change that must be deployed immediately to resolve an active Severity 1 incident or a critical security vulnerability.
* **Approval Authority:** Emergency changes require verbal or written authorization from the Chief Technology Officer (CTO) or their designated delegate.
* **Post-Deployment Review:** All emergency deployments must be logged in the change system within 12 hours of release and formally reviewed by the CAB within 48 hours post-deployment.

## 5. Deployments and Rollbacks
* **Deployment Window:** High-impact changes must be scheduled during the designated maintenance window: Saturdays from 01:00 AM to 05:00 AM local time.
* **Rollback Plan:** Every change request must include a documented rollback plan. If a deployment fails or causes degradation, the team must initiate rollback within 15 minutes of detecting the issue.

## 6. Approvals and Enforcement
* **Standard Changes:** Approved by the immediate Line Manager.
* **Normal Changes:** Approved by the CAB and sign-off from the Technology Risk Lead.
* **Unauthorized Changes:** Any change deployed to production without a registered Change Request will be escalated to Technology Risk for disciplinary review.

***

Synthetic training document. Not an official ttb policy.
