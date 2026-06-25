# Customer Data Handling Policy

**Policy ID:** TTB-SEC-004  
**Effective Date:** November 15, 2024  
**Owner Department:** Information Security  

## 1. Access Controls and Need-to-Know
Customer data is a critical asset at ttb Policy Assistant Demo Bank. This policy defines the operational security controls for accessing, storing, and transmitting customer information.
* **Need-to-Know:** Access to Customer Personally Identifiable Information (PII) and financial records is restricted to employees who require the data to perform their job duties.
* **Access Review Cycle:** Access permissions for databases containing customer PII must be reviewed every 90 days by the Data Owner. Unused accounts must be disabled immediately.

## 2. Storage Location Restrictions
* **No Local Storage:** Customer PII and financial records must never be stored on the local drive (C: drive) of any laptop, desktop, or on external media.
* **Approved Locations:** Customer data must reside only on secure database servers approved by Information Security or on restricted-access ttb SharePoint sites.
* **Temporary Files:** Any temporary files containing customer data created during reporting must be permanently deleted immediately after the task is completed.

## 3. Transmission and Encryption Rules
* **Internal Transmission:** When transmitting customer PII internally, data must be sent via encrypted email or secure file sharing platforms.
* **Third-Party Sharing:** When sharing customer data with authorized external partners (e.g., credit bureaus, regulatory reporting), files must be compressed in a ZIP archive encrypted using the AES-256 standard. The password must be shared via a separate communication channel (e.g., SMS).
* **SFTP Transfer:** All external transfers must use the secure ttb SFTP portal. Sharing customer data via public cloud drives is strictly prohibited.

## 4. Screen Display and Masking Standards
* **Masking Rule:** To prevent visual data leakage in offices or remote workspaces, masking is mandatory for customer account numbers.
* **Standard Mask:** When displayed on staff-facing monitors, only the first 3 and last 4 digits of a customer's account number may be visible, with the middle characters masked (e.g., 123XXXX4567).
* **Full View Exception:** Only customer service agents handling active phone verifications may click to "unmask" the full account number, and all such views are logged.

## 5. Bulk Export Controls
* **Bulk Export Definition:** Any export containing more than 1,000 unique customer records is defined as a bulk export.
* **Required Approvals:** Bulk exports must be pre-approved. The request requires written authorization from both the employee's Department Head and the ttb Data Protection Officer (DPO). The export must be logged in the centralized Data Export Registry.

## 6. Incident Escalation
Any suspected customer data leak, unauthorized access, or accidental sending of customer PII to the wrong recipient must be reported to the Information Security team within 15 minutes of discovery.

***

Synthetic training document. Not an official ttb policy.
