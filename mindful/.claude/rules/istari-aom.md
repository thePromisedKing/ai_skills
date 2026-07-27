# Istari AOM — Team Knowledge (auto-refreshed)

## Relevant Topics
- MIT-5068 — got one feedback - CRITICAL: Race condition in create() method allows concurrent: got one feedback - CRITICAL: Race condition in create() method allows concurrent requests to bypass maxPerWallet limit and name uniqueness checks leading to data corruption.

The create() method performs separate database queries to check the current count of templates and to check for duplicate nam
- istari-aom: # Istari AOM — Team Knowledge  ## Relevant Topics - Changes in docs/FRONTEND_SKILL.md: we will proceed with this custom design prepare the document for this which can be used by AI agents. From the prototype design, identify the components that needs to be built, identify what libraries we will be u
- NE-4 — which one is better suited here, react native or flutter?: which one is better suited here, react native or flutter?
- MIT-6921 — You are working on JIRA ticket MIT-6921: CBDC Retail Checkmarx SCA scan- Maven-c: You are working on JIRA ticket MIT-6921: CBDC Retail Checkmarx SCA scan- Maven-commons-codec:commons-codec-1.11

## Ticket Description
Apache commons-codec before 1.13 is vulnerable to information exposure. The Base32 and Base64 implementation blindly decode invalid string, which can be re-encoded a
- README: # Mithril Backend  Spring Boot application powering the CBUAE digital currency ecosystem.  ---  ## Table of Contents  - [Overview](#overview) - [Module Structure](#module-structure) - [Requirements](#requirements) - [Quick Start](#quick-start) - [Running the Application](#running-the-application)
- Changes in docs/FRONTEND_SKILL.md: we will proceed with this custom design prepare the document for this which can be used by AI agents. From the prototype design, identify the components that needs to be built, identify what libraries we will be using for the build based on design decision we took over here. Prepare the whole workfl
- Changes in docs/FRONTEND_SKILL.md: we will proceed with this custom design prepare the document for this which can be used by AI agents. From the prototype design, identify the components that needs to be built, identify what libraries we will be using for the build based on design decision we took over here. Prepare the whole workfl
- Changes in app/licensing.py: i am gettig Apple could not verify ATS Resume Scorer macos is free of malware that may harm your Mac
- Changes in app/licensing.py: i am gettig Apple could not verify ATS Resume Scorer macos is free of malware that may harm your Mac
- MIT-6921 — You are working on JIRA ticket MIT-6921: CBDC Retail Checkmarx SCA scan- Maven-c: You are working on JIRA ticket MIT-6921: CBDC Retail Checkmarx SCA scan- Maven-commons-codec:commons-codec-1.11

## Ticket Description
Apache commons-codec before 1.13 is vulnerable to information exposure. The Base32 and Base64 implementation blindly decode invalid string, which can be re-encoded a

## Similar Past Work
- MIT-7255: Context for this Checkmarx SCA fix (org.springframework.boot:spring-boot-autoconfigure): 1) This repo's team works on the 'staging' branch, NOT main. Your worktree was cut from main, but open the PR against staging. 2) This is a dependency-version vulnerability fix — same family as MIT-5068 (log4j) and MIT-7019 (logback). Find where spring-boot / spring-boot-autoconfigure version is pinned (likely backend/gradle.properties or the Spring Boot plugin/BOM in root build.gradle), bump to the Checkmarx fix version, and verify with: ./gradlew -q :app:dependencyInsight --dependency org.springframework.boot:spring-boot-autoconfigure --configuration runtimeClasspath. 3) Do NOT git commit or git push without presenting the diff for review first — present all changes as text. 4) Check the ticket's SCA finding for the exact CVE and fixed-in version before bumping. (similarity: 0.95)
- MIT-6917: IMPORTANT UPDATE: The team works on the STAGING branch — open your PR against 'staging', not 'main' (qrcode-service/pom.xml is identical on both, so your fix applies cleanly). Additional context from the full Checkmarx CSV (12 findings, scanned 2026-07-07, all RiskState=ToVerify, none with exploitable path): the jdom 1.1.3 finding you own is the only one needing a code change, via the pom's maven-surefire-report-plugin 3.0.0-M9 plugin chain. The jackson-core/databind 2.15.4 findings are manifest-level: requested by resteasy-jackson2-provider 6.2.9 (from keycloak-admin-client 26.0.5) but Gradle's jackson2 BOM 2.21.4 forces them up in all real classpaths — no action, but worth one line in your PR description. otel 1.60.1, jackson 2.18.7, commons-codec 1.11 findings do not exist on staging (otel has been 1.62.0 since May, jackson BOM 2.21.4 since Jul 2) — stale scan targets, no action. Keep scope to: pom surefire-report-plugin bump + log4j-core 2.25.3→2.25.4 in the same pom. (similarity: 0.88)
- topic-authservice-discussion-mr1okrth: AuthService discussion (similarity: 0.52)
  Outcome: completed
  Learnings: prepare a .md file that AI agents can work on for these issues
- NE-4: NE-4 — which one is better suited here, react native or flutter? (similarity: 0.47)
  Outcome: completed
  Learnings: which one is better suited here, react native or flutter?
- bootstrap-claude-istari-aom: istari-aom (similarity: 0.44)
  Outcome: completed
  Learnings: # Istari AOM — Team Knowledge  ## Relevant Topics - Changes in docs/FRONTEND_SKILL.md: we will proceed with this custom design prepare the document for this which can be used by AI agents; From the prototype design, identify the components that needs to be built, identify what libraries we will be u
