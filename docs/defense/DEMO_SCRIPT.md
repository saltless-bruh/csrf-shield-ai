# Demo Video Script — CSRF Shield AI

> **Purpose:** Step-by-step narration script for recording the project demo video.
> **Target Length:** ~5 minutes
> **Tools Needed:** Terminal, screen recorder (OBS / QuickTime / built-in), web browser

---

## Pre-Recording Setup

1. Open a terminal at the project root (`csrf-shield-ai/`)
2. Activate the virtual environment: `source .venv/bin/activate`
3. Ensure the TUI binary is built: `cd cmd/tui && go build -o ../../csrf-shield-tui main.go && cd ../..`
4. Have `data/sample_har/vulnerable.har` ready
5. Set terminal font size large enough for recording (~16pt)
6. Set terminal to at least 120×30 characters

---

## Scene 1 — Introduction (~30 seconds)

**[Show README.md in the terminal or editor]**

**Narration:**

> "This is CSRF Shield AI — an AI-powered security analysis tool that detects Cross-Site Request Forgery vulnerabilities in web applications. It combines 11 static analysis rules with a Random Forest ML classifier to produce quantified risk scores from 0 to 100."

**Action:** Scroll through the README briefly to show features list.

---

## Scene 2 — Installation (~30 seconds)

**[Type commands in terminal]**

```bash
# Show Python and Go versions
python3 --version
go version

# Install the Python package
pip install -e .
```

**Narration:**

> "The tool requires Python 3.10+ and Go 1.21+. Installation is a simple pip install. The Go TUI is compiled to a single binary."

---

## Scene 3 — CLI Analysis (~60 seconds)

**[Type and run the analysis command]**

```bash
csrf-shield analyze -i data/sample_har/vulnerable.har -o /tmp/demo_report.json -f json
```

**Narration:**

> "Let's analyze a sample HAR file containing vulnerable HTTP traffic. The tool parses the HAR file, reconstructs session flows, detects the authentication mechanism, runs static analysis with all 11 CSRF rules, applies ML classification, and calculates the final risk score."

**[Wait for output, then highlight key lines]**

> "We can see it found 3 CSRF findings — missing token, missing SameSite cookie, and no referer validation — resulting in a CRITICAL risk score of 87 out of 100."

---

## Scene 4 — JSON Report (~30 seconds)

**[View the generated report]**

```bash
cat /tmp/demo_report.json | python3 -m json.tool | head -40
```

**Narration:**

> "The JSON report contains the risk score, risk level, all findings with their severity and evidence, ML probability, and remediation recommendations. This can be integrated into CI/CD pipelines for automated security checks."

---

## Scene 5 — HTML Report (~30 seconds)

**[Generate and open HTML report]**

```bash
csrf-shield analyze -i data/sample_har/vulnerable.har -o /tmp/demo_report.html -f html
```

**[Open /tmp/demo_report.html in a web browser]**

**Narration:**

> "The HTML report provides a visual representation with color-coded risk indicators, making it easy to share with team members and stakeholders."

---

## Scene 6 — Interactive TUI (~90 seconds)

**[Launch the TUI]**

```bash
./csrf-shield-tui --input data/sample_har/vulnerable.har
```

**Narration:**

> "Now let's explore the interactive Terminal UI. The TUI uses Vim-style navigation — j and k to move, Tab to switch panels, Enter to select."

**Demo steps:**

1. **[Show sessions panel]** — "The left panel shows all session flows. We can see the auth mechanism detected for each."
2. **[Navigate with j/k]** — "Navigate between sessions using j and k."
3. **[Tab to exchanges]** — "Tab switches to the exchanges panel, showing individual HTTP requests."
4. **[Press Enter to analyze]** — "Press Enter or 'a' to start analysis. Watch the real-time progress."
5. **[Show results]** — "The analysis engine panel shows findings, risk score, and recommendations."
6. **[Press 'e' to export]** — "Press 'e' to export a report directly from the TUI."
7. **[Press F1 for help]** — "F1 shows all available keyboard shortcuts."
8. **[Press 'q' to quit]** — "Press 'q' to quit with a confirmation dialog."

---

## Scene 7 — ML Training (~30 seconds)

**[Show training command]**

```bash
csrf-shield train --data data/training/ --output models/csrf_model.pkl
```

**Narration:**

> "The tool also includes a training pipeline. It trains both Random Forest and XGBoost classifiers, evaluates them against our accuracy targets, and serializes the best model. Our Random Forest achieved 100% accuracy with 100% recall on the test set."

---

## Scene 8 — Closing (~15 seconds)

**Narration:**

> "CSRF Shield AI combines static analysis with machine learning to provide deeper, more accurate CSRF detection than traditional rule-based scanners. The quantified 0–100 risk scoring enables teams to prioritize remediation efforts effectively. Thank you for watching."

---

## Post-Production Checklist

- [ ] Verify all commands executed successfully in recording
- [ ] Check audio is clear and narration matches actions
- [ ] Add title card at beginning with project name and group
- [ ] Add end card with GitHub URL and documentation links
- [ ] Export as MP4, target resolution 1920×1080
- [ ] Total length should be 4–6 minutes

---

> **Deliverable:** D7 — Demo Video (Script)
> **Requirement Reference:** PROPOSAL.md §14
