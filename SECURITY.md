# Infrahub - Security Policy

We are committed to maintaining the security of Infrahub and its users. We deeply appreciate any effort to discover and responsibly disclose security vulnerabilities. This policy outlines the process for reporting security issues to our team.

## When Should I Report a Vulnerability?

* You think you discovered a potential security vulnerability in Infrahub
* You are unsure how a vulnerability affects Infrahub
* You think you discovered a vulnerability in another project that Infrahub depends on

## When Should I NOT Report a Vulnerability?

* You need help configuring Infrahub security settings (such as external authentication)
* You need help applying security related updates
* Your issue is not security related

## Reporting a Vulnerability

If you believe you have found a security vulnerability in Infrahub, please report it via our **private and secure channels**. Do not disclose the vulnerability publicly (e.g., on GitHub Issues, social media, or forums) until we have had a chance to address it.

1. **Use the GitHub Security Advisory feature:** This is the preferred method for reporting vulnerabilities. It provides a confidential channel for communication and automatically handles private disclosure.
    * **[Report a Vulnerability](https://github.com/opsmill/infrahub/security/advisories/new)**

2. **Contact us via email (alternative):** If you are unable to use the GitHub Advisory feature, you may send an email to **opensource-security@opsmill.com**.

***

## Information to Include in a Report

To help us triage and resolve the issue as quickly as possible, please provide as much of the following information as you can:

* **Vulnerability Summary:** A brief, clear description of the vulnerability.
* **Steps to Reproduce:** Detailed, step-by-step instructions that allow us to replicate the issue.
* **Affected Components:**
  * The version, tag, or commit hash of the Infrahub source code.
  * Full path(s) of any relevant file(s).
* **Configuration:** Any specific configuration or environment settings required to reproduce the issue.
* **Impact:** Describe the potential impact of the vulnerability, including how an attacker could exploit it.
* **Proof-of-Concept (PoC):** If available, include a PoC or exploit code to demonstrate the issue.

***

## Timeline for Resolution and Disclosure

We are committed to resolving security vulnerabilities in a timely and coordinated manner. Our general timeline for this process, based on industry best practices, is as follows:

1. **Initial Triage (1-3 business days):** We will acknowledge receipt of your report within this timeframe. Our team will perform an initial assessment to validate the vulnerability and determine its severity.
2. **Patch Development (Time Varies):** Once the vulnerability is confirmed, our engineering team will begin working on a fix. The time required for this step depends on the complexity of the issue. We will keep you updated on our progress.
3. **Coordinated Disclosure (Typically 90 days):** Upon the development of a patch or a solid mitigation strategy, we will work with you to coordinate a public disclosure. The standard industry timeline for this is **90 days** from the initial report. This period allows us to ensure a fix is widely available before the vulnerability is made public.
4. **CVE Assignment:** As part of the coordinated disclosure, we will request a Common Vulnerabilities and Exposures (CVE) identifier for the issue. The CVE ID provides a standardized name for the vulnerability, allowing for easier tracking and communication across the security community.
