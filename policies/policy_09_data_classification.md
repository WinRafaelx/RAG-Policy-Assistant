# Data Classification Policy

**Policy ID:** TTB-SEC-003  
**Effective Date:** November 15, 2024  
**Owner Department:** Information Security  

## 1. Classification Framework Overview
To protect information assets effectively, ttb Policy Assistant Demo Bank classifies all data based on its sensitivity, value, and the potential negative impact of unauthorized disclosure. All data created or handled by ttb employees must fall into one of four classification levels.

## 2. Classification Levels and Definitions
1. **Public:** Information that has been formally approved for public release. Disclosure causes no risk to the bank or its customers.
   * *Examples:* Public marketing brochures, press releases, annual reports.
2. **Internal:** Standard business operational data intended for internal staff. Unauthorized disclosure would cause minimal disruption.
   * *Examples:* Internal phone directories, organization charts, team meeting minutes.
3. **Confidential:** Sensitive business or customer data. Unauthorized disclosure could cause financial, operational, or reputational damage.
   * *Examples:* Customer Personally Identifiable Information (PII) like home addresses and phone numbers, vendor contracts, internal policy drafts.
4. **Restricted:** Highly sensitive data requiring maximum security controls. Unauthorized disclosure would result in severe financial penalties, regulatory sanctions, or critical operational impact.
   * *Examples:* Customer financial account numbers, balances, Social Security Numbers (SSNs), tax IDs, cryptographic keys, and merger and acquisition details.

## 3. Labeling and Encryption Controls
* **Header & Footer:** All documents classified as Restricted must display the word "RESTRICTED" in the header and footer in a 12pt bold red font.
* **Digital Encryption:** Restricted data must be encrypted using ttb's Information Rights Management (IRM) system. Access must be restricted to explicitly authorized active employees.
* **Storage restriction:** Restricted data must never be stored on local drives or shared network folders without AES-256 encryption at rest.

## 4. Classification Changes and Upgrades
* **Authority to Classify:** The Data Owner (the business lead responsible for the data's creation or management) is responsible for determining the initial classification.
* **Review Cycle:** Data owners must review the classification of databases and file repositories annually.
* **Approval for Upgrades/Downgrades:** Any classification changes for a database or dataset must be formally approved in writing by the Data Owner.

## 5. Security Exceptions
Any deviation from the security controls defined for Confidential or Restricted data (e.g., sharing Restricted data via an external communication channel) must be documented in a Risk Acceptance Form. The exception must be approved by the Chief Information Security Officer (CISO) and is valid for a maximum of 12 months.

***

Synthetic training document. Not an official ttb policy.
