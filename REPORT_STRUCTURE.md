# DesignVoyager Course Report Structure

## Objectives
- Page Limit: 8 pages (IEEE two-column, excluding references)
- A systems-type paper: describing system architecture, methodology, and experimental results

---

## 1. Introduction (~1-1.2 pages)

### 1.1 Challenges in Traditional Game Design

Traditional game design workflows face three core problems:

1. **Reinventing the wheel**: Designers are unaware of similar mechanics in other games, leading to redundant work
2. **Inefficient trial-and-error cycles**: Lack of systematic methods to evaluate mechanic quality (playability, balance, strategic depth)
3. **Difficult knowledge accumulation**: Excellent game mechanics remain isolated in designers' minds, academic papers, or oral tradition, making them difficult to reuse

### 1.2 Core Capabilities of Our System

To address these challenges, we propose **DesignVoyager**, which provides three key capabilities:

1. **Automated Evaluation**: Use AI agents (MCTS) + game simulators to quickly test mechanic playability, balance, and strategic depth
2. **Knowledge Accumulation**: Generate new mechanics iteratively via LLM, store verified mechanics in a semantically searchable library
3. **Accelerated Design**: Future game designers can directly select pre-verified mechanics from the library instead of starting from scratch each time

### 1.3 System Innovation Points

1. **Adaptive Repair Cycle**: When generated mechanics fail, the system automatically identifies issues and repairs them rather than discarding them
2. **User Prompt**: User can decide which kind of mechanism they want in a iteration of system process
3. **Deduplication & Library Management**: Rather than simply accumulating all generated mechanics, actively filter similar mechanics to ensure library diversity and representativeness
4. **Library Reuse Validation**: Use the accumulated library to generate new games, validating library utility and creating a virtuous cycle

---

## 2. Background

---

## 3. Methods (~2.5 pages)

### 3.1 Proposal Module

### 3.2 Playtest Module

### 3.3 Verification Module

### 3.4 Library Module

### 3.5 Integration & System Flow

---

## 4. Results (~2.3-2.5 pages)

### 4.1 Evaluation Protocol & Setup

### 4.2 Board vs Card Comparison 

#### 3.2.1 Framework Stability & Ability Comparison

#### 3.2.2 Library Growth, Deduplication Effects & Revising Effect

#### 3.2.3 Metrics Comparison

Playability, Depth, Balance_gap .....

### 3.3 Detailed Case Study

---

## 5. Conclusion

---

## Page Budget Summary

| Section | Target Pages | Notes |
|---------|-------------|-------|
| Introduction | 1.0-1.2 | Problem, capabilities, innovation |
| Background | 1.0 |  |
| Methods | 2.5 | 5 modules + integration |
| Results | 2.3-2.5 | Setup + Board vs Card + Case Study + Efficiency |
| Conclusion | 0.3-0.5 | Summary of contributions |
| **Total (excluding references)** | **~7.5 pages** | 0.5 page buffer remaining |

---

