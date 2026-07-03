# Architecture Refactor - Aegis AI v2

Read the following files completely before making any changes:

- ABOUT.md
- AGENTS.md
- TASK.md

Do NOT add random features.

Do NOT generate placeholder implementations.

Do NOT remove any existing functionality.

The current project is feature complete for Version 1.

The goal is NOT to build more APIs.

The goal is to refactor the architecture into the AI Engineering Workspace described in ABOUT.md.

---

## Current Problem

The application currently behaves like this:

User
↓

Select Agent

↓

Run Agent

↓

LLM

↓

Response

This makes every agent independent.

The Planner is optional.

The agents do not collaborate.

Repository intelligence is only used for retrieval.

---

## Target Architecture

The application should instead behave like this:

User

↓

Planner

↓

Intent Understanding

↓

Project Context Builder

↓

Repository Intelligence

↓

Knowledge Retrieval

↓

Planner decides which agents are required

↓

Execute selected agents

↓

Merge responses

↓

Human Approval (if required)

↓

Execute MCP tools (only if approved)

↓

Update Memory

↓

Return structured response

---

## Core Principles

Planner is the brain.

Agents are workers.

Agents never communicate directly.

Agents never call MCP directly.

Agents never query PostgreSQL directly.

Agents never perform vector search directly.

Everything goes through shared services.

---

## Introduce a Context Builder

Create a dedicated Context Builder service.

Responsibilities:

- Gather repository metadata
- Gather repository summary
- Gather dependency graph
- Gather architecture analysis
- Gather semantic search results
- Gather document search results
- Gather previous memory
- Gather workflow state

Return a single structured Project Context.

Every agent must receive only this context.

No agent should perform retrieval itself.

---

## Repository Intelligence Layer

Separate repository ingestion from repository understanding.

Repository Intelligence should become a first-class subsystem.

It should maintain:

- Repository summary
- Framework detection
- Languages
- Dependency graph
- Service graph
- API routes
- Architecture layers
- Entry points
- Repository health

This information should be persisted.

Agents consume this instead of rescanning repositories.

---

## Planner Refactor

The Planner must become mandatory.

The user never manually selects which agents should execute.

Instead:

User Request

↓

Planner

↓

Determine intent

↓

Select required agents

↓

Build execution plan

↓

Execute agents

↓

Merge outputs

↓

Return final answer

Examples:

"Explain authentication"

↓

Repository Agent

↓

Knowledge Agent

↓

Return combined explanation

------------------------

"Review deployment"

↓

Infrastructure Agent

↓

Repository Agent

↓

Deploy Agent

↓

Return deployment report

------------------------

"Investigate build failure"

↓

Incident Agent

↓

Knowledge Agent

↓

Repository Agent

↓

Return RCA

---

## Agent Responsibilities

Every agent must:

Receive:

- Project Context
- User Intent
- Planner Instructions

Return:

- Structured Result
- Confidence Score
- Recommendations
- Follow-up actions

No agent performs orchestration.

---

## MCP Layer

Planner decides whether MCP tools are required.

Planner invokes Tool Registry.

Tool Registry invokes MCP.

MCP returns structured results.

Agents never communicate with MCP directly.

---

## Memory Refactor

Memory should become:

Execution Memory

Conversation Memory

Repository Memory

Semantic Memory

Planner queries memory.

Agents only receive memory through Context Builder.

---

## AIOps Direction

The project should evolve toward an AI Operations Platform rather than a repository chatbot.

Future workflows should support:

- Incident Investigation
- Deployment Analysis
- Infrastructure Reasoning
- Change Impact Analysis
- Root Cause Analysis
- Engineering Knowledge
- Operational Automation

Design the architecture so these capabilities can be added without major refactoring.

---

## Important

This is an architectural refactor.

Do NOT remove existing APIs.

Do NOT break the frontend.

Prefer introducing services over changing endpoints.

Maintain backward compatibility.

Refactor incrementally.

Stop after completing the architectural refactor and provide a summary of:

- New architecture
- New services
- Updated execution flow
- Remaining work for Version 2