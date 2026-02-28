# 📚 API Reference — CSRF Shield AI

> **Status:** Final
> **Last Updated:** February 28, 2026

---

## 1. CLI Commands

The `csrf-shield` command-line tool provides two primary commands:

### `analyze`

Runs the pipeline to analyze a specified HAR file and output a JSON or HTML report.

- `--input`, `-i`: (Required) Path to the HAR file.
- `--output`, `-o`: (Optional) Path to save the report (default: `report.json`).
- `--format`, `-f`: (Optional) Report format, either `json` or `html`.

### `train`

Trains the Random Forest model using the features extracted from the training data.

- `--data`, `-d`: (Required) Path to the directory containing labeled HAR/Session flows.
- `--output`, `-o`: (Optional) Path to save the `.pkl` model.

---

## 2. Core Data Models (`src/input/models.py`)

- **`HttpExchange`**: Represents a single request-response pair parsed from a HAR file. Fields include request URL, method, headers, cookies, body, response status, headers, and body.
- **`SessionFlow`**: Groups `HttpExchange` objects associated with the same session identifier (e.g., cookie or token) and maintains chronological order.
- **`Finding`**: Represents a triggered static rule, encapsulating a `rule_id`, description, severity, and the specific exchange that triggered the rule.
- **`AnalysisResult`**: The final output for a `SessionFlow`, featuring the array of findings, ML probability score, and the aggregated risk score/level.

---

## 3. HAR Parser API (`src/input/har_parser.py`)

- **`parse_har_file(file_path: Path) -> List[HttpExchange]`**: Reads a `.har` file, validating and extracting request/response pairs into standardized `HttpExchange` instances.
- **`HarParseError`**: Exception raised during file parsing errors or invalid JSON structures.

---

## 4. Static Analyzer API (`src/analysis/static_analyzer.py`)

- **`StaticAnalyzer`**: Orchestrates 11 static analysis heuristic checks across all requests in a `SessionFlow`. Loadable via configuration.
  - **`analyze(flow: SessionFlow) -> List[Finding]`**: Executes enabled checks and aggregates potential CSRF indicators into findings.
- **`rules.csrf_XXX`**: Individual module files (e.g., `csrf_001.py`, `csrf_002.py`) encapsulating logic tailored to specific vulnerabilities like missing origin headers or weak SameSite cookie policies.

---

## 5. Feature Extractor API (`src/analysis/feature_extractor.py`)

- **`FeatureExtractor`**: Transforms a raw `SessionFlow` into a unified feature vector containing 14 features necessary for ML model ingestion.
- **Methods**:
  - **`extract(flow: SessionFlow) -> np.ndarray`**: Encodes categorical data (HTTP methods, Auth mechanism) and normalizes numerical values (Token Entropy, Score averages).

---

## 6. ML Predictor API (`src/ml/predictor.py`)

- **`Predictor`**: Loads serialized scikit-learn models (`.pkl`) and computes the probabilistic likelihood of CSRF vulnerabilities.
  - **`predict(features: np.ndarray) -> float`**: Returns a probability score `[0.0 - 1.0]`.
- **`HeuristicsBoost` (`src/ml/heuristics.py`)**: Conditionally overrides or strictly boosts theoretical probability based on definitive risk indicators matching critical static rules.

---

## 7. Risk Scorer API (`src/scoring/risk_scorer.py`)

- **`RiskScorer.calculate()`**: Blends the normalized static severity score with the ML probability, producing a final Risk Score (0-100) and classifying it into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.
- Adheres to predefined context modifiers (e.g., financial impact paths or administrative subdomains) configured in `settings.yaml`.

---

## 8. Report Generator API (`src/output/report_generator.py`)

- **`generate_json_report(results: List[AnalysisResult]) -> str`**: Dumps results to NDJSON or nicely formatted JSON output for system integration.
- **`generate_html_report(results: List[AnalysisResult], template: Path) -> str`**: Renders a human-readable Jinja2 HTML summarizing the risk landscape and remediation tasks.

---

## 9. Configuration Schema (`config/rules.yaml` & `config/settings.yaml`)

### **`settings.yaml`**

- `logging.verbosity`: Default log verbosity level.
- `model.path`: Fixed path to the exported binary model.
- `scoring.weights`: Distribution ratios for static versus ML weighting logic.

### **`rules.yaml`**

Contains the definitions for all 11 security checks (`CSRF-001` to `CSRF-011`), specifying the `id`, `name`, `active_status`, and `base_severity`. Used by the `StaticAnalyzer` to dynamically load required module endpoints.
