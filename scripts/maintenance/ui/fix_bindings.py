from pathlib import Path

repo_root = Path(__file__).resolve().parents[3]
target_file = repo_root / "internal/ui/keybindings.go"

with target_file.open("r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if '{"", ' in line and ("'q'" in line or "'?'" in line or "'e'" in line or "'r'" in line or "'j'" in line or "'k'" in line or "'h'" in line or "'l'" in line or "'a'" in line or "'A'" in line or "'x'" in line or "'c'" in line or "'f'" in line or "'/'" in line):
        continue  # skip
    if '{"quitmodal", \'y\', gocui.ModNone, a.handleConfirmQuit}' in line:
        for panel in ["PanelSessions", "PanelExchanges", "PanelAnalysis"]:
            for char, fn in [
                ('q', 'handleQuit'), ('?', 'handleHelp'), ('e', 'handleExport'),
                ('r', 'handleRestart'), ('j', 'handleDown'), ('k', 'handleUp'),
                ('h', 'handlePrevPanel'), ('l', 'handleTab'), ('a', 'handleAnalyze'),
                ('A', 'handleAnalyzeAll'), ('x', 'handleRemove'), ('c', 'handleCopyCURL'),
                ('f', 'handleFilter'), ('/', 'handleFilter')
            ]:
                new_lines.append(f'\t\t{{{panel}, \'{char}\', gocui.ModNone, a.{fn}}},\n')
        new_lines.append('\t\t{"help", \'q\', gocui.ModNone, a.handleEsc},\n')
        new_lines.append(line)
    else:
        new_lines.append(line)

with target_file.open("w") as f:
    f.writelines(new_lines)
print("Done3")
