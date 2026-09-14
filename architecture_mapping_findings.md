# Autonomous Merchandise Discovery Architecture: Code Mapping Findings

## 1. Overview
The current codebase for the Autonomous Merchandise Discovery MVP perfectly aligns with the proposed architecture outlined in the document. The codebase successfully implements the 17-stage funnel designed to progressively winnow down broad identity groups into high-quality merchandise artwork.

The project follows a clean architectural approach, separating domain logic (the stages) from application orchestration (workflow management) and infrastructure (databases, AI providers).

## 2. Code Structure vs. Architecture Flow
The 17 stages described in the document are fully mapped into individual files inside the `src/merchandise_discovery/domain/stages` directory.

| Document Stage | Code Implementation | Executor Role |
| :--- | :--- | :--- |
| **Stage 1**: Seed Discovery | `stage_01_seed_discovery.py` | Generates starting points (identities) from seed sources. |
| **Stage 2**: Identity Universe Expansion | `stage_02_identity_expansion.py` | Expands base seeds into specific identity dimensions. |
| **Stage 3**: Intersection Generation | `stage_03_intersection_generation.py` | Combines identities into intersections. |
| **Stage 4**: Coherence and Exp. Hypothesis | `stage_04_coherence_hypothesis.py` | Scores intersections based on logical coherence. |
| **Stage 5**: Pre-Research Filter | `stage_05_pre_research_filter.py` | Deterministic system logic to filter out weak intersections. |
| **Stage 6**: Niche Research | `stage_06_niche_research.py` | Gathers external real-world evidence (mocked or via OpenAI web search). |
| **Stage 7**: Experience Mining | `stage_07_experience_mining.py` | Extracts recurring frustrations and jokes from the research. |
| **Stage 8**: Niche Opportunity Scoring | `stage_08_opportunity_scoring.py` | Evaluates and scores niches using qualitative and quantitative data. |
| **Stage 9**: Merchandise Concept Gen. | `stage_09_concept_generation.py` | Uses reasoning providers to create concepts from experiences. |
| **Stage 10**: Single-Call Concept Critique | `stage_10_concept_critique.py` | Evaluates generated concepts based on authenticity, humor, etc. |
| **Stage 11**: Optional IP/Similarity Check | `stage_11_similarity_ip_check.py` | Checks concepts for potential IP issues or duplicates. |
| **Stage 12**: Final Concept Selection | `stage_12_final_selection.py` | Ranks and selects the highest scoring concepts for artwork. |
| **Stage 13**: Structured Design Brief | `stage_13_design_brief.py` | Uses reasoning providers to structure a design brief for the artwork. |
| **Stage 14**: Grok Prompt Compilation | `stage_14_prompt_compilation.py` | Systematically converts the brief into a prompt for image generation. |
| **Stage 15**: Artwork Generation | `stage_15_artwork_generation.py` | Image provider generates the artwork variants. |
| **Stage 16**: Single-Call Artwork Critique | `stage_16_artwork_critique.py` | Evaluates the resulting artwork against the design brief. |
| **Stage 17**: Human Approval | `stage_17_human_approval.py` | Final evaluation point for the surviving artwork candidates. |

## 3. Workflow Orchestration
The flow is orchestrated through `src/merchandise_discovery/application/workflow_orchestrator.py` and executed via `src/merchandise_discovery/application/discovery_stage_executor.py`. 

- **State Management:** The orchestrator correctly handles passing payloads between stages. For example, Stage 8 validates its input by loading output from Stage 6 (Research) and Stage 7 (Mining), exactly as described in the architecture document where "evidence-backed opportunities" are required.
- **Provider Injection:** `discovery_stage_executor.py` injects dependencies like `ResearchProvider`, `ReasoningProvider`, and `ImageProvider` directly into the stages. This adheres to the rule that stage logic must remain decoupled from specific AI SDKs.
- **Cost Efficiency Logic:** Cost-efficient logic filtering (stages 5, 8, 11) is applied properly before handing heavy tasks to the `reasoning_provider` (stages 9, 10, 13) or the `image_provider` (stage 15).

## 4. Current State (MVP Dummy Data)
As described in your prompt and the `README.md`, the pipeline currently defaults to using local fixture providers (`src/merchandise_discovery/ui/fixtures.py`). 
- **Mocking Strategy:** This allows the pipeline to safely generate data at each of the 17 stages without making actual calls to external APIs, thus preserving your credits. 
- **Live Mode:** External AI usage is supported by configuring `MVP_PROVIDER_MODE=live` and providing the relevant `OPENAI_API_KEY` and `XAI_API_KEY` via an `.env` file. When enabled, Stages 6, 9, 10, 13 use OpenAI, and Stage 15 uses the image generation model.

## 5. Summary and Next Steps
The codebase provides a robust, clean architectural skeleton that maps 1-to-1 with the proposed document. The state machine, continuous worker polling, Streamlit dashboard, and stage-by-stage pipelines are fully implemented using placeholder data.

**To transition from the MVP's dummy data to actual live operations:**
1. You can test live interactions by setting `MVP_PROVIDER_MODE=live` and adding your API keys.
2. The UI dashboard (`app.py`) can be customized to answer the Scope Decisions in Section 10 of the PDF, allowing a human reviewer to interact directly with the output of Stage 16.
