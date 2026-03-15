import re

with open("internal/ui/keybindings.go", "r") as f:
    text = f.read()

# Instead of literal match, we do regex or replace line by line
# Remove all the global character bindings:
chars_to_remove = ['q', '?', 'e', 'r', 'j', 'k', 'h', 'l', 'a', 'A', 'x', 'c', 'f', '/']
for char in chars_to_remove:
    # {"", 'q', gocui.ModNone, a.handleQuit},
    pattern = r'\{\"\", \'' + char + r'\', gocui.ModNone, a\.\w+\}, *\n'
    text = re.sub(pattern, "", text)

# Insert the panel-specific ones right before 'quitmodal' block
insert_block = """\
"""
for panel in ["PanelSessions", "PanelExchanges", "PanelAnalysis"]:
    for char, fn in [
        ('q', 'handleQuit'), ('?', 'handleHelp'), ('e', 'handleExport'),
        ('r', 'handleRestart'), ('j', 'handleDown'), ('k', 'handleUp'),
        ('h', 'handlePrevPanel'), ('l', 'handleTab'), ('a', 'handleAnalyze'),
        ('A', 'handleAnalyzeAll'), ('x', 'handleRemove'), ('c', 'handleCopyCURL'),
        ('f', 'handleFilter'), ('/', 'handleFilter')
    ]:
        insert_block += f'\t\t{{{panel}, \'{char}\', gocui.ModNone, a.{fn}}},\n'
insert_block += '\t\t{"help", \'q\', gocui.ModNone, a.handleEsc},\n'

text = text.replace('{"quitmodal", \'y\', gocui.ModNone, a.handleConfirmQuit},',
                    insert_block + '\t\t{"quitmodal", \'y\', gocui.ModNone, a.handleConfirmQuit},')

with open("internal/ui/keybindings.go", "w") as f:
    f.write(text)
print("Done2")
