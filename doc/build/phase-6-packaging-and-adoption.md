# Phase 6: Packaging And Adoption

## Objective

Package CodeGuardian as an easy-to-install GitHub Action and prepare it for developer adoption.

## Deliverables

- Reusable GitHub Action metadata.
- Example workflow file.
- Starter `.codeguardian/policy.yml`.
- Setup guide.
- Troubleshooting guide.
- Example PR outputs.
- Release and versioning process.
- Marketplace-ready documentation.

## Adoption Flow

```mermaid
flowchart TD
  A["Developer reads README"] --> B["Copies workflow file"]
  B --> C["Adds optional Groq or HF secret"]
  C --> D["Opens test PR"]
  D --> E["CodeGuardian check runs"]
  E --> F["Developer reviews risk report"]
  F --> G["Team sets required check if useful"]
```

## Default Configuration

Recommended default:

```text
mode: advisory
comment_on_low_risk: false
max_findings_in_comment: 5
inline_comments: false
deterministic_fallback: true
model_provider_priority:
  - groq
  - huggingface
  - deterministic
```

## Senior Developer Prompt

```text
You are packaging CodeGuardian AI as a reusable GitHub Action.

Requirements:
- Provide action metadata.
- Provide a minimal workflow example.
- Provide a starter policy file.
- Support Groq, Hugging Face, and deterministic mode.
- Publish GitHub Checks and sticky PR comments.
- Upload report artifacts.
- Include examples for public and private repos.
- Create release versioning rules.
- Add integration tests with fixture PR diffs.

Output:
- Packaging plan
- File structure
- Release process
- Example workflow
- Configuration reference
- Test and validation plan
```

## Product Manager Prompt

```text
You are preparing CodeGuardian AI for developer adoption.

Create the launch and onboarding plan.

Include:
- One-minute product explanation.
- Install steps.
- First successful run criteria.
- Recommended default settings.
- How to make the check required.
- How to configure Groq and Hugging Face.
- Common troubleshooting issues.
- Activation metrics.
```

## User Prompt

```text
I want to install CodeGuardian on this repository.

Give me:
- The workflow file to add.
- The secrets I need.
- The recommended default policy.
- How to open a test PR.
- How to make CodeGuardian a required check.
```

## Acceptance Criteria

- A new user can install in under 10 minutes.
- The first PR produces a check.
- No model key is required for first run.
- Docs explain Groq and Hugging Face setup.
- Required-check setup is documented.
- Releases are versioned and changelogged.

