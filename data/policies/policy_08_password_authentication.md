# Password and Authentication Policy

**Policy ID:** TTB-SEC-002  
**Effective Date:** November 15, 2024  
**Owner Department:** Information Security  

## 1. Scope and Intent
This policy defines the security standards for passwords, access credentials, and multi-factor authentication (MFA) mechanisms used to access systems and applications at ttb Policy Assistant Demo Bank. Strong authentication is a critical defense against unauthorized access to customer data and bank resources.

## 2. Password Complexity Standards
All user-defined passwords for ttb corporate accounts and internal systems must comply with the following complexity rules:
* **Minimum Length:** Passwords must be at least 16 characters in length.
* **Character Requirements:** Passwords must contain characters from at least three of the following groups:
  1. Uppercase letters (A-Z)
  2. Lowercase letters (a-z)
  3. Numerical digits (0-9)
  4. Special characters (e.g., !, @, #, $, %, ^, &, *)
* **Common Patterns:** Passwords must not contain the user's login ID, full name, or dictionary words in sequential order.

## 3. Password Expiration and Rotation
* **Expiration Interval:** Passwords must be changed every 90 calendar days.
* **Renewal Prompt:** The system will prompt users to change their password starting 14 days prior to the expiration date.
* **History Restriction:** Users cannot reuse any of their last 12 passwords.
* **Forced Reset:** If a system account shows signs of compromise, Information Security will initiate a forced password reset immediately.

## 4. Multi-Factor Authentication (MFA) Standards
* **MFA Mandatory:** MFA is mandatory for all access to the ttb corporate network, email systems, and financial databases.
* **Primary MFA Method:** The default and primary MFA method is push notification via the official ttb Authenticator App installed on a corporate-issued mobile phone.
* **Travel Backup:** SMS-based MFA is permitted only as a backup option when an employee is traveling internationally and has verified connection issues with the authenticator app. SMS MFA must be disabled upon return.

## 5. Account Lockout and Unlocking
* **Lockout Threshold:** Accounts will be automatically locked out after 5 consecutive failed login attempts.
* **Lockout Duration:** The automatic account lockout lasts for 30 minutes, after which the account is automatically reset.
* **Immediate Unlock:** If a user needs immediate access, they must contact the IT Service Desk and verify their identity using a pre-registered verbal security phrase.

## 6. Service Account Exemptions
* **Service Accounts:** Automated system-to-system connections (service accounts) are exempt from the 90-day password rotation and MFA rules, provided they use API keys or certificates.
* **Risk Acceptance:** Any service account exemption must be documented, reviewed by the Technology Risk team, and formally approved by the CISO.

***

Synthetic training document. Not an official ttb policy.
