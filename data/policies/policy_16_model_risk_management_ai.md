# Model Risk Management Policy for AI Tools

**Policy ID:** TTB-TECH-002  
**Effective Date:** February 15, 2025  
**Owner Department:** Technology Risk  

## 1. Scope and Inventory Registration
This policy defines the risk management standards for artificial intelligence (AI), machine learning (ML), and large language models (LLMs) used at ttb Policy Assistant Demo Bank.
* **Mandatory Registration:** All AI/ML models, including third-party LLMs and internally developed predictive models, must be registered in the ttb Model Inventory.
* **Inventory Approval:** Model registration requires approval from the AI Center of Excellence (AI COE) Lead.

## 2. Independent Model Validation
* **Validation Requirement:** Prior to deployment into production, every registered AI model must undergo independent validation.
* **Model Validation Group (MVG):** Validation is conducted by the Model Validation Group (MVG), which operates independently of the model developers.
* **Validation Standards:** The MVG reviews the model training data, algorithm selection, bias mitigation, and testing outcomes. A model cannot deploy without an active MVG Approval Certificate.

## 3. Human-in-the-Loop (HITL) Standards
* **HITL Mandated:** A Human-in-the-Loop review process is mandatory for any AI-generated outputs that:
  1. Are directly communicated to retail or corporate customers.
  2. Affect credit risk scoring, lending decisions, or fraud detection reviews.
* **Review Process:** Staff must review and confirm the accuracy and compliance of the AI output before it is finalized or sent.
* **HITL Exception:** Any exceptions to the HITL requirement must be reviewed by the Technology Risk team and approved in writing by the Chief Risk Officer (CRO).

## 4. Continuous Performance Monitoring
* **Drift Monitoring:** AI models in production must be monitored for performance and data drift. Performance reviews must run weekly.
* **Performance Drop Threshold:** If a model's performance drop (e.g., accuracy, precision) exceeds 5% compared to its baseline validation metrics, the model must be automatically disabled or reverted to its previous stable version.
* **Retraining Logs:** All retraining activities must be logged, and retrained models must be re-validated by the MVG.

## 5. Escalation and Governance
If an active AI model exhibits anomalous behavior or generates incorrect outputs (e.g., hallucinations), it must be reported to the Technology Risk team within 2 hours. The model will be suspended pending validation by the Head of Technology Risk.

***

Synthetic training document. Not an official ttb policy.
