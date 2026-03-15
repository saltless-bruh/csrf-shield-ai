import re

with open("internal/ui/export.go", "r") as f:
    content = f.read()

# Replace fake cursor and add terminal cursor placing
old_draw = """// Path Input
pathStr := fmt.Sprintf("  Path:     %s\\n", a.exportPath)
if a.exportFocusIdx == 2 {
pathStr = "\\033[30;47m" + pathStr[:len(pathStr)-1] + "_\\033[0m\\n" // Invert color for focus + cursor
}

fmt.Fprintf(v, "\\n%s%s\\n%s\\n", formatStr, scopeStr, pathStr)
fmt.Fprintf(v, "           [ Enter to Export ]\\n")
}"""

new_draw = """// Path Input
pathStr := fmt.Sprintf("  Path:     %s\\n", a.exportPath)
if a.exportFocusIdx == 2 {
pathStr = "\\033[30;47m" + pathStr[:len(pathStr)-1] + "\\033[0m\\n" // Invert color for focus
}

fmt.Fprintf(v, "\\n%s%s\\n%s\\n", formatStr, scopeStr, pathStr)
fmt.Fprintf(v, "           [ Enter to Export ]\\n")
    
    // Set actual hardware cursor at the end of the path input
    if a.exportFocusIdx == 2 {
        v.SetCursor(12 + len(a.exportPath), 4)
    }
}"""

if old_draw in content:
    content = content.replace(old_draw, new_draw)
    print("Replaced drawExportModal")
else:
    print("WARN: drawExportModal not found")

with open("internal/ui/export.go", "w") as f:
    f.write(content)
