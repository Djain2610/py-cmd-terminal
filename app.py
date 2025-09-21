from flask import Flask, request, jsonify, render_template_string
import os
import sys

# Add the current directory to Python path to import main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the necessary functions from main.py
from main import execute_line_internal

app = Flask(__name__)

# HTML template for the terminal interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Terminal Emulator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background-color: #000;
            color: #fff;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .terminal-header {
            background-color: #1a1a1a;
            padding: 10px 15px;
            border-bottom: 1px solid #333;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .terminal-title {
            font-weight: bold;
            color: #00ff00;
        }

        .terminal-controls {
            display: flex;
            gap: 10px;
        }

        .clear-btn {
            background-color: #333;
            color: #fff;
            border: 1px solid #555;
            padding: 4px 8px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
            transition: background-color 0.2s;
        }

        .clear-btn:hover {
            background-color: #444;
        }

        .terminal-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            padding: 15px;
        }

        #terminal-output {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            background-color: #000;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 14px;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-word;
            border: 1px solid #333;
        }

        .prompt-line {
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }

        .prompt {
            color: #00ff00; /* Green */
            margin-right: 8px;
            font-weight: bold;
        }

        .directory {
            color: #00ffff; /* Cyan */
            margin-right: 8px;
        }

        .input-line {
            display: flex;
            align-items: center;
        }

        #command-input {
            flex: 1;
            background-color: transparent;
            color: #fff;
            border: none;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            outline: none;
            padding: 5px 0;
        }

        #command-input::placeholder {
            color: #888;
        }

        .command-output {
            color: #fff;
            margin-bottom: 5px;
        }

        .command-output.command {
            color: #00ff00; /* Green for commands */
        }

        .command-output.error {
            color: #ff0000; /* Red for errors */
        }

        .command-output.success {
            color: #fff; /* White for output */
        }

        /* Scrollbar styling */
        #terminal-output::-webkit-scrollbar {
            width: 8px;
        }

        #terminal-output::-webkit-scrollbar-track {
            background: #1a1a1a;
        }

        #terminal-output::-webkit-scrollbar-thumb {
            background: #444;
            border-radius: 4px;
        }

        #terminal-output::-webkit-scrollbar-thumb:hover {
            background: #555;
        }

        /* Animation for new lines */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .fade-in {
            animation: fadeIn 0.2s ease-out;
        }
    </style>
</head>
<body>
    <div class="terminal-header">
        <div class="terminal-title">Python Terminal Emulator</div>
        <div class="terminal-controls">
            <button id="clear-btn" class="clear-btn">Clear</button>
        </div>
    </div>
    
    <div class="terminal-container">
        <div id="terminal-output"></div>
        <div class="input-line">
            <span class="prompt" id="current-prompt">jaind:</span>
            <span class="directory" id="current-directory">/Desktop/problem1_codemate</span>
            <span class="prompt">$ </span>
            <input type="text" id="command-input" autocomplete="off" autofocus placeholder="Type a command...">
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const terminalOutput = document.getElementById('terminal-output');
            const commandInput = document.getElementById('command-input');
            const clearBtn = document.getElementById('clear-btn');
            const currentPrompt = document.getElementById('current-prompt');
            const currentDirectory = document.getElementById('current-directory');
            
            // Initialize with welcome message
            addOutputLine('Python Terminal Emulator Ready', 'success');
            addOutputLine('Type "help" for available commands.', 'success');
            
            // Focus input on load
            commandInput.focus();
            
            // Handle command submission
            commandInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    const command = commandInput.value.trim();
                    if (command) {
                        executeCommand(command);
                    }
                    commandInput.value = '';
                }
            });
            
            // Clear button handler
            clearBtn.addEventListener('click', function() {
                terminalOutput.innerHTML = '';
            });
            
            // Function to execute command
            function executeCommand(command) {
                // Display the command
                addOutputLine(`$ ${command}`, 'command');
                
                // Send to backend
                fetch('/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ command: command })
                })
                .then(response => {
                    // Check if response is ok
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    // Try to parse JSON, fallback to text if it fails
                    return response.text().then(text => {
                        // Try to parse as JSON first
                        try {
                            return JSON.parse(text);
                        } catch (e) {
                            // If parsing fails, return the raw text
                            return text;
                        }
                    });
                })
                .then(data => {
                    // If data is a string, treat it as output
                    if (typeof data === 'string') {
                        addOutputLine(data, 'success');
                    } else {
                        // If data is an object, handle normally
                        if (data.output) {
                            addOutputLine(data.output, 'success');
                        }
                        if (data.error) {
                            addOutputLine(data.error, 'error');
                        }
                    }
                })
                .catch(error => {
                    addOutputLine(`Error communicating with backend: ${error.message}`, 'error');
                });
            }
            
            // Function to add output line to terminal
            function addOutputLine(text, type) {
                const line = document.createElement('div');
                line.className = `command-output ${type} fade-in`;
                line.textContent = text;
                terminalOutput.appendChild(line);
                
                // Scroll to bottom
                terminalOutput.scrollTop = terminalOutput.scrollHeight;
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/execute', methods=['POST'])
def execute():
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({"output": "", "error": "No command provided"}), 400
            
        # Execute the command using the function from main.py
        output = execute_line_internal(command, record_history=False)
        
        # Return the output as JSON
        return jsonify({"output": output if output else "", "error": None})
        
    except Exception as e:
        # Log the exception for debugging purposes (this won't be visible to user)
        print(f"Unexpected error in execute route: {e}")
        return jsonify({"output": "", "error": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
