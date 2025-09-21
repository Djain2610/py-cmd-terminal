from flask import Flask, request, render_template_string
from main import execute_line_internal  # import your existing terminal logic

app = Flask(__name__)

# Keep the history in memory with a pre-filled welcome message
history = """Welcome to PyTerminal Web!
Type commands below and press Enter to execute.

Example commands:
- help
- pwd
- ls
- touch file1.txt
- mkdir test
- mv file1.txt test/
- cpu
- mem
"""

# Minimal HTML for terminal UI
HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PyTerminal Web</title>
<style>
body { background: #1e1e1e; color: #ffffff; font-family: monospace; padding: 1em; }
input { width: 100%; background: #1e1e1e; color: #fff; border: none; padding: 0.5em; font-family: monospace; }
pre { white-space: pre-wrap; }
</style>
</head>
<body>
<pre>{{output}}</pre>
<form method="post">
<input autofocus autocomplete="off" name="cmd" placeholder="Enter command..." />
</form>
<script>
const input = document.querySelector('input');
input.addEventListener("keydown", function(event) {
    if(event.key === "Enter") { this.form.submit(); }
});
input.focus();
</script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    global history
    if request.method == "POST":
        cmd = request.form.get("cmd", "")
        if cmd:
            # Run your Python terminal logic
            output = execute_line_internal(cmd)
            history += f"$ {cmd}\n{output}\n"
    return render_template_string(HTML, output=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
