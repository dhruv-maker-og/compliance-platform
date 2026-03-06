# PCI-DSS v4.0 Compliance Evidence Collection Skill

## Overview
This skill guides the agent through collecting evidence for PCI-DSS v4.0 compliance.
PCI-DSS (Payment Card Industry Data Security Standard) has 12 principal requirements
organized into 6 goals. For each requirement, this skill defines what evidence to
collect, which tools to use, and what constitutes a pass or gap.

## How to Use This Skill
1. Load this file at the start of a PCI-DSS evidence collection session.
2. Identify which requirements the user wants to audit (specific controls or "all").
3. For each requirement, follow the evidence collection steps below.
4. Use the `evidence_assembler` tool to structure collected data by control ID.
5. Use the `gap_analyzer` tool with the structured evidence and `controls.json` to determine pass/fail.
6. Use the `report_generator` tool to produce the final report.

---

## Goal 1: Build and Maintain a Secure Network and Systems

### Requirement 1: Install and Maintain Network Security Controls

#### 1.1 — Processes and mechanisms for network security controls are defined and understood
- **Evidence needed**: Network security policy documents, network diagrams, data flow diagrams
- **Tools**: `github:github_search_code` (search for network policy docs, diagrams in repos), `azure:azure_nsg_rules` (list all NSGs)
- **Collection steps**:
  1. Search GitHub repos for files matching `*network*diagram*`, `*network*policy*`, `*data*flow*`
  2. List all Azure NSGs and their associated subnets
  3. Check for documented review dates on network policies
- **Pass criteria**: Network policy document exists and was reviewed within last 12 months; network diagram exists; NSG rules are documented

#### 1.2 — Network security controls (NSCs) are configured and maintained
- **Evidence needed**: Firewall/NSG rule configurations, change management records
- **Tools**: `azure:azure_nsg_rules`, `azure:azure_activity_log` (NSG changes)
- **Collection steps**:
  1. Retrieve all NSG rules across subscriptions
  2. Query activity log for NSG rule changes in last 90 days
  3. Verify inbound rules follow least-privilege (no overly permissive 0.0.0.0/0 rules on sensitive ports)
- **Pass criteria**: NSG rules exist for all subnets with CDE workloads; no allow-all inbound rules on ports 22, 3389, 1433, 3306; changes have documented justification

#### 1.3 — Network access to and from the cardholder data environment is restricted
- **Evidence needed**: CDE network segmentation configuration, access control lists
- **Tools**: `azure:azure_nsg_rules`, `azure:azure_resource_list` (identify CDE resources)
- **Collection steps**:
  1. Identify resources tagged as CDE (tag: `environment:cde` or similar)
  2. Verify NSG rules on CDE subnets restrict traffic to only necessary sources
  3. Check for network isolation (separate VNet or subnet)
- **Pass criteria**: CDE resources are in dedicated subnets; NSG rules restrict inbound to known IPs/ranges; outbound restricted to necessary destinations

#### 1.4 — Network connections between trusted and untrusted networks are controlled
- **Evidence needed**: Perimeter firewall configs, DMZ architecture
- **Tools**: `azure:azure_resource_list` (Azure Firewall, Application Gateway, WAF)
- **Collection steps**:
  1. List Azure Firewall and WAF instances
  2. Retrieve firewall rule collections
  3. Verify anti-spoofing measures are in place
- **Pass criteria**: Perimeter firewall exists; default-deny rules in place; WAF protecting web-facing apps

#### 1.5 — Risks to the CDE from computing devices connecting to untrusted networks are mitigated
- **Evidence needed**: VPN configurations, endpoint security policies
- **Tools**: `entra-id:get_conditional_access_policies`, `azure:azure_defender_recommendations`
- **Collection steps**:
  1. List conditional access policies requiring compliant devices
  2. Check Defender for Cloud endpoint protection recommendations
- **Pass criteria**: Conditional access requires device compliance for CDE access; endpoint protection enforced

---

### Requirement 2: Apply Secure Configurations to All System Components

#### 2.1 — Processes and mechanisms for secure configurations are defined and understood
- **Evidence needed**: Configuration standards documentation, hardening guides
- **Tools**: `github:github_search_code` (search for hardening docs, config standards)
- **Collection steps**:
  1. Search repos for configuration standards, hardening guides, CIS benchmarks
  2. Verify documentation covers all system types (servers, databases, network devices)
- **Pass criteria**: Configuration standards document exists; references industry benchmarks (CIS, STIG)

#### 2.2 — System components are configured and managed securely
- **Evidence needed**: Default passwords changed, unnecessary services disabled, security parameters configured
- **Tools**: `azure:azure_defender_recommendations`, `azure:azure_sql_servers`, `azure:azure_storage_accounts`
- **Collection steps**:
  1. Get Defender for Cloud secure score and recommendations
  2. Check SQL servers for default configurations (e.g., TLS enforcement, audit logging)
  3. Check storage accounts for secure settings (HTTPS-only, TLS 1.2)
  4. Verify no default credentials in use (check Defender recommendations)
- **Pass criteria**: Secure score above threshold; TLS 1.2 enforced everywhere; no critical Defender recommendations open

#### 2.3 — Wireless environments are configured and managed securely
- **Evidence needed**: Wireless security policies, wireless network configurations (if applicable)
- **Tools**: `github:github_search_code` (wireless policy docs)
- **Note**: For cloud-only environments, this may be marked N/A with justification

---

## Goal 2: Protect Account Data

### Requirement 3: Protect Stored Account Data

#### 3.1 — Processes and mechanisms for protecting stored account data are defined and understood
- **Evidence needed**: Data retention policies, data disposal procedures
- **Tools**: `github:github_search_code`, `purview:get_data_policies`
- **Collection steps**:
  1. Search for data retention and disposal policy documents
  2. Query Purview for data lifecycle policies
- **Pass criteria**: Data retention policy exists; specifies retention periods; disposal procedures documented

#### 3.2 — Storage of account data is kept to a minimum
- **Evidence needed**: Data inventory, data flow mapping, justification for stored data
- **Tools**: `purview:get_data_classifications`, `purview:get_scan_results`
- **Collection steps**:
  1. Query Purview for data classifications related to payment/financial data
  2. Review scan results for PCI-related data discoveries
  3. Verify data minimization practices are documented
- **Pass criteria**: Data inventory exists; sensitive data locations are known; retention justification documented

#### 3.3 — Sensitive authentication data (SAD) is not stored after authorization
- **Evidence needed**: Application configurations, database schema review
- **Tools**: `github:github_search_code` (search for SAD storage patterns), `purview:get_data_classifications`
- **Collection steps**:
  1. Search code repos for patterns that might store CVV, full track data, or PIN data
  2. Check Purview classifications for SAD-type data
- **Pass criteria**: No SAD stored post-authorization; code review shows no SAD persistence patterns

#### 3.4 — Access to displays of full PAN is restricted
- **Evidence needed**: PAN masking configurations, display policies
- **Tools**: `github:github_search_code` (masking logic in code)
- **Collection steps**:
  1. Search application code for PAN display/masking logic
  2. Verify masking shows at most first 6 and last 4 digits
- **Pass criteria**: PAN masking logic exists; displays limited to BIN + last 4 digits

#### 3.5 — PAN is secured wherever it is stored
- **Evidence needed**: Encryption configurations (at rest), key management
- **Tools**: `azure:azure_storage_accounts`, `azure:azure_sql_servers`, `azure:azure_keyvault_list`
- **Collection steps**:
  1. Check storage account encryption (SSE with CMK or Microsoft-managed keys)
  2. Check SQL TDE (Transparent Data Encryption) status
  3. Verify Key Vault exists for key management
  4. Check encryption key rotation policies
- **Pass criteria**: All storage encrypted at rest; TDE enabled on all SQL databases; Key Vault in use; keys rotated per policy

---

### Requirement 4: Protect Cardholder Data with Strong Cryptography During Transmission

#### 4.1 — Processes for protecting CHD over open/public networks are defined
- **Evidence needed**: Encryption in transit policies, TLS configurations
- **Tools**: `azure:azure_storage_accounts`, `azure:azure_sql_servers`, `github:github_search_code`
- **Collection steps**:
  1. Verify HTTPS-only enabled on all storage accounts
  2. Check minimum TLS version on SQL servers (must be 1.2+)
  3. Search application code for TLS configuration
- **Pass criteria**: TLS 1.2+ enforced; HTTPS-only on all public endpoints; no deprecated cipher suites

#### 4.2 — PAN is protected with strong cryptography during transmission
- **Evidence needed**: Network encryption configurations, certificate management
- **Tools**: `azure:azure_keyvault_list` (certificates), `azure:azure_resource_list` (Application Gateways, API Management)
- **Collection steps**:
  1. List certificates in Key Vault (verify validity, key strength)
  2. Check Application Gateway SSL policies
  3. Verify end-to-end encryption for data flows containing PAN
- **Pass criteria**: Valid TLS certificates; RSA 2048+ or ECC 256+ key sizes; end-to-end encryption verified

---

## Goal 3: Maintain a Vulnerability Management Program

### Requirement 5: Protect All Systems and Networks from Malicious Software

#### 5.1 — Processes for protecting against malware are defined and understood
- **Evidence needed**: Anti-malware policies, endpoint protection configurations
- **Tools**: `azure:azure_defender_recommendations`, `entra-id:get_conditional_access_policies`
- **Collection steps**:
  1. Check Defender for Cloud for endpoint protection coverage
  2. Verify anti-malware solutions deployed on all applicable systems
  3. Search for anti-malware policy documents
- **Pass criteria**: Endpoint protection enabled on all VMs; anti-malware policy documented; real-time scanning enabled

#### 5.2 — Malicious software is prevented or detected and addressed
- **Evidence needed**: Anti-malware scan logs, detection/response records
- **Tools**: `azure:azure_defender_recommendations`
- **Collection steps**:
  1. Check Defender for Cloud alerts related to malware
  2. Verify automatic updates enabled for anti-malware signatures
- **Pass criteria**: Anti-malware solutions actively scanning; signatures updated automatically; alerts configured

#### 5.3 — Anti-malware mechanisms are active, maintained, and monitored
- **Evidence needed**: Monitoring configurations, alert rules
- **Tools**: `azure:azure_defender_recommendations`
- **Pass criteria**: Anti-malware cannot be disabled by users; monitoring alerts configured

#### 5.4 — Anti-phishing mechanisms protect users
- **Evidence needed**: Email security configurations, phishing training records
- **Tools**: `entra-id:get_conditional_access_policies`, `github:github_search_code` (security training docs)
- **Pass criteria**: Email filtering in place; phishing awareness training conducted

---

### Requirement 6: Develop and Maintain Secure Systems and Software

#### 6.1 — Processes for secure development are defined and understood
- **Evidence needed**: SDLC documentation, secure coding training records
- **Tools**: `github:github_search_code` (SDLC docs, coding standards)
- **Collection steps**:
  1. Search for SDLC, secure coding, and development standards documents
  2. Verify secure development training records exist
- **Pass criteria**: SDLC documented; includes security at each phase; developers trained annually

#### 6.2 — Bespoke and custom software is developed securely
- **Evidence needed**: Code review processes, security testing in SDLC
- **Tools**: `github:github_branch_protection`, `github:github_pull_requests`
- **Collection steps**:
  1. Check branch protection rules (require PR reviews, status checks)
  2. Verify code review is mandatory before merge
  3. Check for security scanning in CI pipelines (SAST, DAST references)
- **Pass criteria**: Branch protection enabled on main branches; PR review required; automated security testing in CI

#### 6.3 — Security vulnerabilities are identified and addressed
- **Evidence needed**: Vulnerability scanning results, patching records
- **Tools**: `azure:azure_defender_recommendations`, `github:github_search_code` (dependency scanning)
- **Collection steps**:
  1. Query Defender for vulnerability assessment results
  2. Check GitHub for Dependabot or similar dependency scanning configuration
  3. Verify vulnerability remediation SLAs
- **Pass criteria**: Regular vulnerability scanning in place; critical vulnerabilities remediated within 30 days; dependency scanning enabled

#### 6.4 — Public-facing web applications are protected
- **Evidence needed**: WAF configurations, web application security testing
- **Tools**: `azure:azure_resource_list` (WAF, Application Gateway, Front Door)
- **Collection steps**:
  1. List WAF instances and their rule configurations
  2. Verify WAF is in prevention mode (not just detection)
  3. Check for OWASP rule sets enabled
- **Pass criteria**: WAF deployed for public web apps; prevention mode enabled; OWASP top 10 rules active

---

## Goal 4: Implement Strong Access Control Measures

### Requirement 7: Restrict Access to System Components and Cardholder Data by Business Need to Know

#### 7.1 — Processes for restricting access are defined and understood
- **Evidence needed**: Access control policies, role definitions
- **Tools**: `entra-id:get_directory_roles`, `github:github_search_code` (access policy docs)
- **Collection steps**:
  1. Retrieve directory role definitions and assignments
  2. Search for access control policy documents
  3. Verify least-privilege principle is documented
- **Pass criteria**: Access control policy exists; RBAC implemented; least-privilege documented

#### 7.2 — Access to system components and data is appropriately defined and assigned
- **Evidence needed**: RBAC configurations, access reviews
- **Tools**: `entra-id:get_directory_roles`, `entra-id:get_privileged_role_assignments`, `entra-id:get_group_memberships`
- **Collection steps**:
  1. List all privileged role assignments
  2. Check for access review configurations
  3. Verify role assignments follow documented access control policy
- **Pass criteria**: RBAC in use; privileged roles limited; access reviews conducted quarterly

#### 7.3 — Access to system components and data is managed via an access control system
- **Evidence needed**: Access control system configurations (RBAC, ACLs)
- **Tools**: `entra-id:get_directory_roles`, `azure:azure_resource_list` (RBAC assignments)
- **Pass criteria**: Centralized access control (Entra ID RBAC); default-deny for all resources

---

### Requirement 8: Identify Users and Authenticate Access to System Components

#### 8.1 — Processes for user identification and authentication are defined and understood
- **Evidence needed**: Authentication policies, identity management documentation
- **Tools**: `entra-id:get_conditional_access_policies`, `github:github_search_code` (auth policies)
- **Pass criteria**: Authentication policy documented; covers all user types

#### 8.2 — User identification and related accounts are strictly managed
- **Evidence needed**: User account inventory, shared account controls
- **Tools**: `entra-id:get_service_principals`, `entra-id:get_app_registrations`
- **Collection steps**:
  1. List all user accounts (look for shared/generic accounts)
  2. List service principals and app registrations
  3. Verify unique IDs for all users; no shared accounts for CDE access
- **Pass criteria**: Unique user IDs assigned; no shared/generic accounts for CDE; inactive accounts disabled within 90 days

#### 8.3 — Strong authentication is established and managed
- **Evidence needed**: MFA configurations, password policies
- **Tools**: `entra-id:get_mfa_status`, `entra-id:get_conditional_access_policies`
- **Collection steps**:
  1. Query MFA enrollment status for all users
  2. Check conditional access policies requiring MFA
  3. Verify password complexity and rotation policies
- **Pass criteria**: MFA enforced for all CDE access; MFA enforced for all admin access; minimum password length 12 characters

#### 8.4 — Multi-factor authentication (MFA) is implemented for all access into the CDE
- **Evidence needed**: MFA enforcement for CDE resources
- **Tools**: `entra-id:get_mfa_status`, `entra-id:get_conditional_access_policies`
- **Pass criteria**: MFA enforced for all CDE-bound access methods (console, API, VPN)

#### 8.5 — Multi-factor authentication systems are configured to prevent misuse
- **Evidence needed**: MFA configuration details (lockout, re-enrollment)
- **Tools**: `entra-id:get_conditional_access_policies`
- **Pass criteria**: MFA lockout after failed attempts; re-enrollment requires identity verification

#### 8.6 — Use of application and system accounts is strictly managed
- **Evidence needed**: Service account inventory, credential rotation
- **Tools**: `entra-id:get_service_principals`, `azure:azure_keyvault_list`
- **Collection steps**:
  1. List service principals and their credential expiry dates
  2. Check Key Vault for credential rotation policies
  3. Verify interactive login disabled for service accounts
- **Pass criteria**: Service accounts inventoried; credentials rotate per policy; no interactive login for service accounts

---

### Requirement 9: Restrict Physical Access to Cardholder Data

#### 9.1–9.4 — Physical access controls
- **Note**: Physical access controls are largely outside the scope of cloud-based automated evidence collection
- **Evidence needed**: Physical security policies, visitor logs, media handling procedures
- **Tools**: `github:github_search_code` (physical security policy docs)
- **Collection steps**:
  1. Search for physical security policy documents
  2. Note that cloud provider (Azure) physical security is covered by Azure SOC 2 / PCI-DSS attestations
- **Pass criteria**: Physical security policies documented; Azure compliance certifications referenced for data center controls

---

## Goal 5: Regularly Monitor and Test Networks

### Requirement 10: Log and Monitor All Access to System Components and Cardholder Data

#### 10.1 — Processes for logging and monitoring are defined and understood
- **Evidence needed**: Logging policies, log management documentation
- **Tools**: `github:github_search_code` (logging policy), `azure:azure_activity_log`
- **Pass criteria**: Logging policy documented; defines what to log, retention periods, monitoring responsibilities

#### 10.2 — Audit logs are implemented to support detection of anomalies
- **Evidence needed**: Logging configurations, audit log samples
- **Tools**: `azure:azure_activity_log`, `azure:azure_sql_servers` (auditing config), `azure:azure_storage_accounts` (diagnostic settings)
- **Collection steps**:
  1. Verify Azure Activity Log is enabled and exported
  2. Check SQL auditing is enabled
  3. Verify storage diagnostic logging enabled
  4. Check that logs capture: user identification, event type, date/time, success/failure, resource affected
- **Pass criteria**: Audit logging enabled on all CDE systems; logs capture required fields; logs exported to central location

#### 10.3 — Audit logs are protected from destruction and unauthorized modifications
- **Evidence needed**: Log protection configurations, immutable storage
- **Tools**: `azure:azure_storage_accounts` (immutable blob storage), `azure:azure_activity_log`
- **Pass criteria**: Logs stored in immutable storage; access to logs restricted; log integrity monitoring in place

#### 10.4 — Audit logs are reviewed to identify anomalies
- **Evidence needed**: Log review procedures, alerting configurations, SIEM integration
- **Tools**: `azure:azure_defender_recommendations`, `github:github_search_code` (incident response docs)
- **Pass criteria**: Automated alerting for security events; daily log review process documented; SIEM or equivalent in use

#### 10.5 — Audit log history is retained and available for analysis
- **Evidence needed**: Log retention configurations
- **Tools**: `azure:azure_storage_accounts`, `azure:azure_activity_log`
- **Pass criteria**: At least 12 months of audit log history; 3 months immediately available for analysis

#### 10.6 — Time-synchronization mechanisms support consistent time across all systems
- **Evidence needed**: NTP configurations
- **Tools**: `azure:azure_resource_list`
- **Note**: Azure platform provides time synchronization by default; document reliance on Azure NTP
- **Pass criteria**: Systems use Azure-provided NTP; time source documented

#### 10.7 — Failures of critical security control systems are detected and addressed
- **Evidence needed**: Monitoring for security control failures, alerting
- **Tools**: `azure:azure_defender_recommendations`
- **Pass criteria**: Alerts configured for logging failures; response procedures documented

---

### Requirement 11: Test Security of Systems and Networks Regularly

#### 11.1 — Wireless access points are identified and monitored
- **Evidence needed**: Wireless AP inventory, rogue detection
- **Note**: For Azure-only, may be N/A (document cloud-only posture)
- **Pass criteria**: Wireless inventory maintained or N/A documented with justification

#### 11.2 — Wireless access points are identified and monitored
- **Note**: Duplicate of 11.1 in some PCI-DSS mappings; handle as above

#### 11.3 — External and internal vulnerabilities are regularly scanned
- **Evidence needed**: Vulnerability scan reports (ASV for external, internal scans)
- **Tools**: `azure:azure_defender_recommendations`
- **Collection steps**:
  1. Query Defender for Cloud vulnerability assessment results
  2. Check for ASV scan records (may need manual evidence)
- **Pass criteria**: Quarterly external ASV scans by approved vendor; quarterly internal vulnerability scans; remediation for critical/high within 30 days

#### 11.4 — External and internal penetration testing is regularly performed
- **Evidence needed**: Penetration test reports
- **Tools**: `github:github_search_code` (pentest reports, remediation tracking)
- **Pass criteria**: Annual penetration testing conducted; covers network and application layers; findings remediated

#### 11.5 — Network intrusions and unexpected file changes are detected and responded to
- **Evidence needed**: IDS/IPS configurations, file integrity monitoring
- **Tools**: `azure:azure_defender_recommendations`
- **Pass criteria**: IDS/IPS in place at CDE boundaries; file integrity monitoring for critical files

#### 11.6 — Unauthorized changes on payment pages are detected and responded to
- **Evidence needed**: Change detection mechanisms for payment pages
- **Tools**: `github:github_search_code` (CSP configuration, SRI), `azure:azure_resource_list` (WAF)
- **Pass criteria**: Change/tamper detection for payment pages; alerts for unauthorized modifications

---

## Goal 6: Maintain an Information Security Policy

### Requirement 12: Support Information Security with Organizational Policies and Programs

#### 12.1 — A comprehensive information security policy is established and maintained
- **Evidence needed**: Information security policy documents
- **Tools**: `github:github_search_code` (security policy files)
- **Pass criteria**: Security policy exists; reviewed annually; covers all PCI-DSS requirements

#### 12.2 — Acceptable use policies are defined and understood
- **Evidence needed**: Acceptable use policy documents
- **Tools**: `github:github_search_code`
- **Pass criteria**: Acceptable use policy documented; covers technology use

#### 12.3 — Risks to the CDE are formally identified, evaluated, and managed
- **Evidence needed**: Risk assessment documents, risk register
- **Tools**: `github:github_search_code` (risk assessment docs)
- **Pass criteria**: Annual risk assessment conducted; risk register maintained; risks prioritized

#### 12.4 — PCI DSS compliance is managed
- **Evidence needed**: PCI compliance program documentation, responsibility assignments
- **Tools**: `github:github_search_code`
- **Pass criteria**: Compliance program documented; responsibilities assigned; quarterly reviews

#### 12.5 — PCI DSS scope is documented and validated
- **Evidence needed**: Scope documentation, data flow diagrams
- **Tools**: `github:github_search_code`
- **Pass criteria**: Scope documented; includes all CDE systems; validated annually

#### 12.6 — Security awareness education is an ongoing activity
- **Evidence needed**: Security training program, training records
- **Tools**: `github:github_search_code` (training program docs)
- **Pass criteria**: Annual security awareness training; covers PCI-DSS responsibilities; training records maintained

#### 12.7 — Personnel are screened to reduce risks from insider threats
- **Evidence needed**: Background check policies
- **Tools**: `github:github_search_code`
- **Pass criteria**: Background check policy exists for CDE-accessing personnel

#### 12.8 — Risk to information assets from third-party service provider relationships is managed
- **Evidence needed**: TPSP inventory, contracts, compliance monitoring
- **Tools**: `github:github_search_code` (vendor management docs)
- **Pass criteria**: TPSP inventory maintained; contracts include security requirements; TPSP compliance monitored

#### 12.9 — Third-party service providers support PCI DSS compliance of their customers
- **Evidence needed**: TPSP compliance documentation (if entity is a service provider)
- **Note**: Applicable only if the entity is a service provider
- **Pass criteria**: (If applicable) PCI-DSS responsibilities documented between parties

#### 12.10 — Security incidents and suspected security incidents are responded to immediately
- **Evidence needed**: Incident response plan, incident response team, testing records
- **Tools**: `github:github_search_code` (incident response plan), `azure:azure_defender_recommendations`
- **Collection steps**:
  1. Search for incident response plan documents
  2. Check Defender alerts and response history
  3. Verify IR plan tested annually
- **Pass criteria**: IR plan exists; IR team designated; plan tested annually; covers containment, eradication, recovery

---

## Post-Collection Workflow
1. After collecting evidence for all requested controls, call `evidence_assembler` with all raw evidence data
2. Call `gap_analyzer` with the assembled evidence bundle and the `controls.json` reference
3. Call `report_generator` with the gap analysis results to produce the final report
4. Present the report to the user with:
   - Executive summary (overall compliance posture, # controls passed/failed/gaps)
   - Detailed findings per requirement
   - Gap remediation recommendations
   - Evidence artifacts inventory
