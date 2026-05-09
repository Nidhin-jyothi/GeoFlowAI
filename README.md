# GeoFlowAI — AI-Powered Geospatial Workflow Automation

> **Automate complex GIS analysis pipelines using natural language.** GeoFlowAI is a multi-agent AI system that converts plain-English geospatial queries into fully executable QGIS workflows — no GIS expertise required.

---

## Table of Contents

1. [Abstract](#abstract)
2. [System Architecture](#system-architecture)
3. [Agent Pipeline](#agent-pipeline)
4. [Technology Stack](#technology-stack)
5. [Project Structure](#project-structure)
6. [Data Catalog](#data-catalog)
7. [Knowledge Base & RAG](#knowledge-base--rag)
8. [GUI Design](#gui-design)
9. [Key Engineering Decisions](#key-engineering-decisions)
10. [Installation & Setup](#installation--setup)
11. [Usage](#usage)
12. [Example Workflows](#example-workflows)
13. [Limitations & Future Work](#limitations--future-work)

---

## Abstract

GeoFlowAI bridges the gap between natural language and geospatial analysis by implementing a **four-agent AI pipeline** that:

1. **Plans** a logical GIS workflow from a natural language query
2. **Structures** the plan into a machine-readable JSON execution schema
3. **Generates** executable PyQGIS scripts for each step
4. **Executes** scripts headlessly in QGIS, with self-debugging on failure

The system uses **Google Gemini LLMs**, **Retrieval-Augmented Generation (RAG)** with FAISS vector stores, and **QGIS 3.40** as the geospatial processing backend. A unified **tkinter-based HUD GUI** provides real-time visual feedback across all pipeline stages.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          main.py (Orchestrator)                        │
│                    Chains all agents in one process                     │
├─────────────┬──────────────┬──────────────────┬────────────────────────┤
│  Agent 1    │   Agent 2    │     Agent 3      │       Agent 4          │
│  PLANNER    │  SCHEMATIZER │    CODE GEN      │   EXECUTOR + DEBUGGER  │
│             │              │                  │                        │
│ Natural     │ Text Plan →  │ JSON Schema →    │ PyQGIS Script →        │
│ Language →  │ JSON         │ PyQGIS Scripts   │ Run + Auto-Fix         │
│ Text Plan   │ Execution    │                  │                        │
│             │ Schema       │                  │                        │
├─────────────┼──────────────┼──────────────────┼────────────────────────┤
│ Gemini 2.5  │ Gemini 2.5   │ Gemini 2.0 Flash │ Gemini 2.5 Flash       │
│ Flash       │ Flash        │                  │ (Debugging)            │
│ + Thinking  │              │                  │                        │
├─────────────┴──────────────┴──────────────────┴────────────────────────┤
│                    RAG Layer (FAISS + HuggingFace Embeddings)          │
│                    all-MiniLM-L6-v2 sentence-transformers              │
├────────────────────────────────────────────────────────────────────────┤
│                    QGIS 3.40.8 (Headless Processing Backend)          │
├────────────────────────────────────────────────────────────────────────┤
│                    Supabase (Cloud Data Sync — optional)               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Pipeline

### Agent 1 — Planner (`agent1_planner.py`)

| Property | Value |
|----------|-------|
| **Model** | `gemini-2.5-flash` (with native thinking) |
| **Input** | Natural language query (e.g., *"Find flood-prone areas in Kerala"*) |
| **Output** | `outputs/step1_plan.txt` — A text workflow plan with algorithm IDs |
| **RAG** | Retrieves relevant QGIS algorithm documentation from FAISS |
| **Thinking** | Uses Gemini's native `thinking_config` to show its reasoning process |

**How it works:**
- Receives user query + data catalog (`data_schema.json`) + algorithm index (`all_alg_ids.txt`)
- RAG retrieves relevant QGIS documentation chunks for grounding
- Gemini generates a step-by-step plan with specific QGIS algorithm IDs
- Streaming output shows both the model's thinking process and final plan

---

### Agent 2 — Schematizer (`agent2_schematizer.py`)

| Property | Value |
|----------|-------|
| **Model** | `gemini-2.5-flash` |
| **Input** | `outputs/step1_plan.txt` — Text plan from Agent 1 |
| **Output** | `outputs/workflow_plan.json` — Machine-readable execution schema |
| **RAG** | Retrieves algorithm parameter details from FAISS |
| **Validation** | Cross-checks algorithm IDs against `all_alg_ids.txt` |

**How it works:**
- Parses the text plan and maps each step to verified QGIS algorithm IDs
- Resolves input file paths from `data_schema.json`
- Generates complete parameter dictionaries (enums as integer indices, CRS handling, extent strings)
- Injects reprojection steps when distance-based operations need metric CRS (EPSG:3857)
- Validates all algorithm IDs against the known QGIS algorithm index

**Key Rules Enforced:**
- Replaces `qgis:rastercalculator` with `gdal:rastercalculator` (headless compatibility)
- Auto-injects `native:reprojectlayer` for distance operations on degree-based CRS
- Uses `native:extractbyexpression` for multi-value OR filters

---

### Agent 3 — Code Generator (`agent3_codegen.py`)

| Property | Value |
|----------|-------|
| **Model** | `gemini-2.0-flash` |
| **Input** | Individual step from `workflow_plan.json` |
| **Output** | PyQGIS scripts (e.g., `step_01_extract_boundary.py`) |
| **RAG** | Retrieves PyQGIS code patterns from FAISS |

**How it works:**
- For each step in the JSON schema, generates a standalone PyQGIS script
- Injects a hardcoded QGIS boilerplate header (`QGIS_HEADER`) that:
  - Initializes `QgsApplication` in headless mode
  - Sets up `sys.path` for QGIS Python plugins
  - Imports `processing` and registers native algorithms
  - Creates a `LoggingFeedback` class to capture QGIS internal messages
- The LLM generates only the task-specific body (no duplicate imports)
- Applies 15 codegen rules including raster alignment, parameter formatting, and error handling

**Key Rules Enforced:**
- Uses `gdal:rastercalculator` instead of `qgis:rastercalculator`
- Pre-aligns rasters with `gdal:warpreproject` before multi-raster calculations
- Strips unsafe parameters from `gdal:cliprasterbymasklayer`
- All code starts at column 0 (no accidental indentation)

---

### Agent 4 — Executor + Debugger (`agent4_run_debug.py`)

| Property | Value |
|----------|-------|
| **Model** | `gemini-2.5-flash` (for debugging) |
| **Input** | Generated PyQGIS script + step metadata |
| **Output** | Executed GIS output files (.shp, .tif) |
| **Retries** | Up to 4 attempts with LLM-powered debugging per step |

**How it works:**
- **Pre-execution cleanup**: Deletes existing output files to prevent OGR conflicts
- **Input sync**: Downloads missing data files from Supabase (optional)
- **Execution**: Runs scripts via `python-qgis-ltr.bat` subprocess
- **Success check**: Verifies (1) no Python traceback, (2) `SUCCESS` in stdout, (3) output file exists on disk
- **Auto-debug**: On failure, sends the error log + code + RAG context to Gemini for a fix
- **Output sync**: Uploads results to Supabase (optional)

**Debugging Rules:**
- Preserves QGIS header boilerplate (never modifies init code)
- Aligns rasters when dimension mismatch errors occur
- Uses exact file paths from the plan context

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **LLM** | Google Gemini 2.5 Flash / 2.0 Flash | Plan generation, code generation, debugging |
| **RAG** | LangChain + FAISS + HuggingFace `all-MiniLM-L6-v2` | Algorithm knowledge retrieval |
| **GIS Engine** | QGIS 3.40.8 (headless via `python-qgis-ltr.bat`) | Geospatial processing |
| **GUI** | tkinter (Python standard library) | Iron Man HUD-themed interface |
| **Cloud Storage** | Supabase Storage | Data sync (optional) |
| **Config** | python-dotenv + `.env` | API key management |
| **Libraries** | `google-genai`, `langchain`, `sentence-transformers`, `faiss-cpu` | Core AI infrastructure |

---

## Project Structure

```
GeoFlowAI/
├── main.py                         # Unified pipeline orchestrator
│
├── agent1_planner.py               # Agent 1: Natural language → text plan
├── agent2_schematizer.py           # Agent 2: Text plan → JSON schema
├── agent3_codegen.py               # Agent 3: JSON step → PyQGIS script
├── agent4_run_debug.py             # Agent 4: Execute + auto-debug scripts
│
├── gui_agent1.py                   # Agent 1 GUI (Cyan/Teal theme)
├── gui_agent2.py                   # Agent 2 GUI (Amber theme)
├── gui_agent3.py                   # Agent 3 GUI (Purple theme)
├── gui_agent4.py                   # Agent 4 standalone GUI
│
├── config.py                       # API keys, paths, directory setup
├── data_schema.json                # Available dataset catalog
├── all_alg_ids.txt                 # 379 valid QGIS algorithm IDs
├── qgis_algorithms_detailed.json   # Full QGIS algorithm parameter reference
│
├── data_manager.py                 # Supabase upload/download client
├── extract_python_code.py          # Strip markdown fences from LLM output
├── build_knowledge_base.py         # Web scraper → FAISS for QGIS docs
├── RAG_agent2.py                   # Alternative RAG builder for Agent 2
├── dump_algos_schema.py            # Scrape QGIS algorithm schemas
│
├── requirements.txt                # Python dependencies
├── .env                            # API keys (not committed)
│
├── data/                           # Geospatial input datasets
│   ├── gadm41_IND_*.shp            # India admin boundaries (Level 0-3)
│   ├── kerala_dem.tif              # Kerala Digital Elevation Model
│   ├── HydroRIVERS_v10_as.shp     # South Asia river network
│   ├── India_PVOUT.tif             # Solar PV output potential
│   ├── India_GHI.tif               # Global Horizontal Irradiation
│   ├── India_DNI.tif               # Direct Normal Irradiation
│   └── southern-zone-*.shp/       # South India OSM road network
│
├── agent2_knowledge_base/          # FAISS vector store (algorithm docs)
├── qgis_knowledge_base/            # FAISS vector store (QGIS docs)
│
└── outputs/                        # Generated scripts & GIS output files
    ├── step1_plan.txt              # Agent 1 output
    ├── workflow_plan.json          # Agent 2 output
    ├── step_*.py                   # Agent 3 generated scripts
    └── *.shp / *.tif              # Final GIS output files
```

---

## Data Catalog

| Dataset | File | Type | Description |
|---------|------|------|-------------|
| India Admin Level 0 | `gadm41_IND_0.shp` | Vector | Country boundary |
| India Admin Level 1 | `gadm41_IND_1.shp` | Vector | State boundaries (36 states/UTs) |
| India Admin Level 2 | `gadm41_IND_2.shp` | Vector | District boundaries |
| India Admin Level 3 | `gadm41_IND_3.shp` | Vector | Sub-district (taluk) boundaries |
| Kerala DEM | `kerala_dem.tif` | Raster | Digital Elevation Model |
| HydroRIVERS South Asia | `HydroRIVERS_v10_as.shp` | Vector | River network (~207 MB) |
| India Solar PVOUT | `India_PVOUT.tif` | Raster | PhotoVoltaic power potential |
| India Solar GHI | `India_GHI.tif` | Raster | Global Horizontal Irradiation |
| India Solar DNI | `India_DNI.tif` | Raster | Direct Normal Irradiation |
| South India Roads (OSM) | `gis_osm_roads_free_1.shp` | Vector | OpenStreetMap road network |

---

## Knowledge Base & RAG

GeoFlowAI uses **Retrieval-Augmented Generation (RAG)** to ground LLM outputs in real QGIS documentation.

### How it works:

1. **Web Scraping** (`build_knowledge_base.py`): Scrapes official QGIS documentation pages for vector/raster algorithm reference
2. **Text Splitting**: Uses `RecursiveCharacterTextSplitter` (chunk size: 1000, overlap: 200)
3. **Embedding**: Encodes chunks with `all-MiniLM-L6-v2` sentence-transformer
4. **Vector Store**: Stores embeddings in FAISS for fast similarity search
5. **Retrieval**: At query time, retrieves top-k relevant chunks and injects them into the LLM prompt

### Two Knowledge Bases:

| Knowledge Base | Directory | Used By | Content |
|---------------|-----------|---------|---------|
| `qgis_knowledge_base/` | Agent 1 | QGIS algorithm documentation |
| `agent2_knowledge_base/` | Agents 2, 3, 4 | Detailed algorithm parameters & PyQGIS patterns |

### Algorithm Index:

- `all_alg_ids.txt`: Contains **379 validated QGIS algorithm IDs** (e.g., `native:buffer`, `gdal:cliprasterbymasklayer`)
- Used by all agents to validate that generated algorithm references actually exist in QGIS
- Generated by `dump_algos_schema.py` which introspects the QGIS Processing registry

---

## GUI Design

The GUI follows an **Iron Man HUD (Heads-Up Display)** aesthetic with three color-coded agent windows:

| Agent | Color Theme | Key Feature |
|-------|------------|-------------|
| Agent 1 — Planner | Cyan/Teal | Arc Reactor spinner, real-time thinking + plan streaming |
| Agent 2 — Schematizer | Amber/Gold | Data stream spinner, JSON syntax-highlighted typewriter |
| Agent 3 — Code Gen + Execute | Purple/Magenta | Pipeline step tracker, code view + execution log tabs |

### GUI Components:

- **`TypewriterText`**: Custom `tk.Text` widget with typewriter animation and syntax highlighting
- **`ArcReactorSpinner`**: Rotating concentric arc canvas animation (Agent 1)
- **`DataStreamSpinner`**: Hexagonal data-stream animation (Agent 2)
- **`CodeParticleSpinner`**: Orbital particle animation (Agent 3)
- **`PipelineTerminal`**: Timestamped log view with color-coded message categories

### Orchestrator (`main.py`):

- Creates a hidden `tk.Tk()` root window
- Each agent opens as a `tk.Toplevel` window
- Completion callbacks chain agents: Plan ready → launch Agent 2 → Schema ready → launch Agent 3
- 3-second delays between agent launches for visual clarity
- Auto-opens QGIS Desktop with output layers when the pipeline completes

---

## Key Engineering Decisions

### 1. Raster Dimension Alignment
**Problem:** `gdal_calc.py` crashes if input rasters differ by even 1 pixel in dimensions.
**Solution:** Rule 15 in CodeGen forces `gdal:warpreproject` alignment of all secondary rasters to match the primary raster's exact extent and resolution before any `gdal:rastercalculator` operation.

### 2. Output File Conflict Prevention
**Problem:** OGR fails with "is not a directory" when shapefile components exist from previous runs.
**Solution:** `_cleanup_output()` in Agent 4 deletes all companion files (`.shp`, `.dbf`, `.shx`, `.prj`, `.cpg`, `.tif`, etc.) before each step execution.

### 3. CRS-Aware Distance Operations
**Problem:** Buffer/distance operations produce wrong results when input layers use geographic CRS (degrees).
**Solution:** Rule 7 in the Schematizer auto-injects `native:reprojectlayer` to EPSG:3857 (meters) before any distance-based algorithm.

### 4. Headless QGIS Compatibility
**Problem:** `qgis:rastercalculator` doesn't work in headless/script mode.
**Solution:** System-wide rule enforced across all agents to use `gdal:rastercalculator` with single-letter variable formulas (A, B, C...).

### 5. Native Thinking Display
**Problem:** Users want to see the AI's reasoning process alongside the output.
**Solution:** Gemini 2.5 Flash's `thinking_config` streams thoughts in dimmed italic cyan, followed by the plan in normal white — all in the same output box. Only the final plan text is saved.

---

## Installation & Setup

### Prerequisites

- **Python 3.12+**
- **QGIS 3.40.8** (installed at `C:\Program Files\QGIS 3.40.8\`)
- **Google Gemini API Key**

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/Nidhin-jyothi/GeoFlowAI.git
cd GeoFlowAI

# 2. Create virtual environment
python -m venv env
.\env\Scripts\Activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys
# Create a .env file with:
GEMINI_API_KEY=your_gemini_api_key_here
SUPABASE_URL=your_supabase_url        # optional
SUPABASE_KEY=your_supabase_key        # optional

# 5. Build knowledge bases (first time only)
python build_knowledge_base.py

# 6. Place geospatial data in data/ directory
# (See Data Catalog section above)
```

---

## Usage

### Full Automated Pipeline
```bash
python main.py
```
1. Agent 1 window opens → enter your query → click ⚡ GENERATE PLAN
2. Agent 2 window auto-opens → structures the plan into JSON
3. Agent 3 window auto-opens → generates code + executes all steps
4. QGIS Desktop opens with the output layers

### Individual Agents (Manual Mode)
```bash
python gui_agent1.py    # Plan generation only
python gui_agent2.py    # Schema generation only (reads step1_plan.txt)
python gui_agent3.py    # Code generation + execution (reads workflow_plan.json)
```

---

## Example Workflows

### 1. Solar Potential Analysis
**Query:** *"Find regions in Rajasthan where Solar PVOUT > 5.0 and GHI > 4.5"*

| Step | Algorithm | Output |
|------|-----------|--------|
| 1 | `native:extractbyattribute` | Rajasthan boundary |
| 2 | `gdal:cliprasterbymasklayer` | Clipped PVOUT raster |
| 3 | `gdal:cliprasterbymasklayer` | Clipped GHI raster |
| 4 | `gdal:rastercalculator` | Binary suitability raster |
| 5 | `gdal:polygonize` | Suitable region polygons |

### 2. Flood Risk Assessment
**Query:** *"Identify flood-prone areas in Kerala (low elevation, low slope, near rivers)"*

| Step | Algorithm | Output |
|------|-----------|--------|
| 1 | `native:extractbyattribute` | Kerala boundary |
| 2 | `gdal:cliprasterbymasklayer` | Clipped DEM |
| 3 | `gdal:clipvectorbypolygon` | Kerala rivers |
| 4–5 | `native:reprojectlayer` + `native:buffer` | 500m river buffer |
| 6 | `native:slope` | Slope raster |
| 7–9 | `gdal:rastercalculator` × 2 + `native:rasterbooleanand` | Combined risk raster |
| 10–12 | `native:polygonize` + `native:clip` | Flood-prone polygons |

### 3. Highway Accessibility
**Query:** *"Regions in Kerala more than 10km from any National Highway"*

| Step | Algorithm | Output |
|------|-----------|--------|
| 1 | `native:extractbyattribute` | Kerala boundary |
| 2 | `native:extractbyexpression` | National Highways (motorway + primary) |
| 3–4 | `native:reprojectlayer` × 2 | Reprojected to EPSG:3857 |
| 5 | `native:buffer` | 10km buffer around highways |
| 6 | `native:difference` | Regions outside buffer |

---

## Limitations & Future Work

### Current Limitations
- **Data-dependent:** Only works with datasets registered in `data_schema.json`
- **QGIS-specific:** Tied to QGIS 3.40.8 on Windows
- **Network required:** Gemini API calls require internet; Supabase sync optional
- **Single-threaded execution:** Steps execute sequentially, not in parallel

### Future Enhancements
- **Support for more GIS backends:** GRASS GIS, PostGIS
- **Parallel step execution:** Independent steps could run concurrently
- **Result validation agent:** Automated spatial sanity checks on outputs
- **Interactive map preview:** Embed Leaflet/Folium map in the GUI
- **Cross-platform:** Linux/macOS QGIS support
- **User-uploaded data:** Drag-and-drop new datasets into the pipeline

---

## License

This project was developed as an academic project.

---

*Built with ❤️ using Google Gemini AI, QGIS, and Python.*
