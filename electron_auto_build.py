import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import queue

# --- Constants ---
DOWNLOADS_FOLDER = str(Path.home() / "Downloads")
APP_NAME = "ElectronAutoBuild"
TEMP_DIR = os.path.join(os.getcwd(), "temp_build")

# --- Templates ---

# React entry point template
REACT_TEMPLATE = """
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""

# Updated package.json with additional NSIS installer fixes
PACKAGE_JSON = """
{{
  "name": "{app_name_lowercase}",
  "version": "1.0.0",
  "main": "public/electron.js",
  "homepage": "./",
  "scripts": {{
    "start": "react-scripts start",
    "build": "react-scripts build",
    "electron": "electron .",
    "dist": "electron-builder"
  }},
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.303.0"
  }},
  "devDependencies": {{
    "electron": "^27.1.0",
    "electron-builder": "^24.6.4",
    "react-scripts": "5.0.1"
  }},
  "build": {{
    "appId": "com.example.{app_name_lowercase}",
    "productName": "{app_name}",
    "directories": {{
      "output": "dist"
    }},
    "files": [
      "build/**/*",
      "public/electron.js"
    ],
    "win": {{
      "target": "nsis"
    }},
    "nsis": {{
        "oneClick": false,
        "perMachine": false,
        "allowToChangeInstallationDirectory": true,
        "allowElevation": false,
        "runAfterFinish": false,
        "deleteAppDataOnUninstall": true
    }},
    "mac": {{
      "target": "dmg"
    }}
  }}
}}
"""

# Main Electron process file with corrected syntax
ELECTRON_MAIN = """
const { app, BrowserWindow } = require('electron');
const path = require('path');
const url = require('url');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js') // It's good practice to use a preload script
    }
  });

  // and load the index.html of the app.
  const startUrl = url.format({
    pathname: path.join(__dirname, '../build/index.html'),
    protocol: 'file:',
    slashes: true
  });
  win.loadURL(startUrl);

  // Open the DevTools.
  // win.webContents.openDevTools();
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
"""

class ElectronAutoBuildApp:
    def __init__(self, master):
        self.master = master
        master.title(APP_NAME)
        master.geometry("800x700")

        main_frame = tk.Frame(master)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.name_label = tk.Label(main_frame, text="App Name:")
        self.name_label.pack(pady=(0, 0))
        self.name_entry = tk.Entry(main_frame, width=50)
        self.name_entry.pack(pady=5)
        self.name_entry.insert(0, "MyReactElectronApp")

        self.label = tk.Label(main_frame, text="Paste your React App.js code or select a file:")
        self.label.pack(pady=5)

        self.text_area = scrolledtext.ScrolledText(main_frame, height=15)
        self.text_area.pack(fill="both", expand=True, padx=5, pady=5)

        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=5)

        self.upload_button = tk.Button(button_frame, text="Select React File", command=self.load_file)
        self.upload_button.pack(side="left", padx=5)

        self.build_button = tk.Button(button_frame, text="Build Electron App", command=self.start_build)
        self.build_button.pack(side="left", padx=5)

        self.recheck_button = tk.Button(button_frame, text="Recheck Dependencies", command=self.check_and_notify_dependencies)
        self.recheck_button.pack(side="left", padx=5)

        self.log_label = tk.Label(main_frame, text="Build Log:")
        self.log_label.pack(pady=(10, 0))
        self.log_view = scrolledtext.ScrolledText(main_frame, height=10, state='disabled', bg='#f0f0f0', wrap='word')
        self.log_view.pack(fill="both", expand=True, padx=5, pady=5)

        self.status_label = tk.Label(main_frame, text="")
        self.status_label.pack()

        self.build_queue = queue.Queue()
        self.check_and_notify_dependencies()

    def load_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("JavaScript Files", "*.js"), ("All Files", "*.*")])
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as file:
                self.text_area.delete('1.0', tk.END)
                self.text_area.insert(tk.END, file.read())

    def check_node_installed(self):
        missing = []
        for cmd in ["node", "npm", "npx"]:
            if shutil.which(cmd) is None:
                missing.append(cmd)
        return missing

    def check_and_notify_dependencies(self):
        missing = self.check_node_installed()
        if missing:
            msg = f"Missing dependencies: {', '.join(missing)}.\nPlease ensure Node.js, npm, and npx are properly installed and available in your system's PATH."
            messagebox.showerror("Missing Dependencies", msg)
            self.status_label.config(text=f"Missing dependencies: {', '.join(missing)}")
        else:
            self.status_label.config(text="All dependencies detected.")

    def start_build(self):
        self.build_button.config(state="disabled")
        self.upload_button.config(state="disabled")
        self.log_view.config(state='normal')
        self.log_view.delete('1.0', tk.END)
        self.log_view.config(state='disabled')
        
        build_thread = threading.Thread(target=self.build_app_thread, daemon=True)
        build_thread.start()
        
        self.process_queue()

    def process_queue(self):
        try:
            message_type, data = self.build_queue.get_nowait()
            
            if message_type == "log":
                self.log_view.config(state='normal')
                self.log_view.insert(tk.END, data + "\n")
                self.log_view.see(tk.END)
                self.log_view.config(state='disabled')
            elif message_type == "status":
                self.status_label.config(text=data)
            elif message_type == "error":
                messagebox.showerror("Build Failed", data)
                self.status_label.config(text=f"Build failed. See log for details.")
            elif message_type == "success":
                messagebox.showinfo("Success", data)
                self.status_label.config(text="Build successful!")
            elif message_type == "done":
                self.build_button.config(state="normal")
                self.upload_button.config(state="normal")
                return
                
        except queue.Empty:
            pass
        
        self.master.after(100, self.process_queue)

    def run_command_and_stream_output(self, command, cwd, log_fn):
        """
        Runs a command and streams its output to the log function in real-time.
        Handles paths with spaces on Windows by quoting the executable.
        """
        log_fn(f"\n> {' '.join(command)}\n")
        
        is_windows = sys.platform == 'win32'
        if is_windows:
            cmd_list = list(command) 
            if " " in cmd_list[0]:
                cmd_list[0] = f'"{cmd_list[0]}"'
            cmd_to_run = ' '.join(cmd_list)
        else:
            cmd_to_run = command

        process = subprocess.Popen(
            cmd_to_run,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=is_windows,
            bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            log_fn(line.strip())
        
        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def build_app_thread(self):
        """The main build process, running in a separate thread."""
        
        log_messages = []
        def log(message):
            """Puts a log message into the queue and stores it for the log file."""
            print(message)
            log_messages.append(str(message))
            self.build_queue.put(("log", message))

        app_output_folder = None
        try:
            # --- Define output paths BEFORE the main try block ---
            app_name_input = self.name_entry.get().strip()
            sanitized_app_name = ''.join(c for c in app_name_input if c.isalnum() or c in ('-', '_')).strip()
            
            product_name = sanitized_app_name if sanitized_app_name else "MyReactElectronApp"
            package_name = product_name.lower()

            app_output_folder = os.path.join(DOWNLOADS_FOLDER, product_name)
            os.makedirs(app_output_folder, exist_ok=True)

            # --- Start Build Process ---
            log("Step 1: Checking dependencies...")
            missing = self.check_node_installed()
            if missing:
                raise Exception(f"Missing dependencies: {', '.join(missing)}")
            
            npx_path = shutil.which("npx")
            npm_path = shutil.which("npm")
            if not npx_path or not npm_path:
                raise FileNotFoundError("Could not resolve the full path for npx or npm.")
            log("Dependencies found.")

            log("Step 2: Setting up temporary build directory...")
            if os.path.exists(TEMP_DIR):
                log(f"Removing existing temporary directory: {TEMP_DIR}")
                shutil.rmtree(TEMP_DIR, ignore_errors=True)
            os.makedirs(TEMP_DIR)
            log("Temporary directory created.")

            log("Step 3: Creating React app with 'create-react-app'. This may take a while...")
            self.run_command_and_stream_output([npx_path, "create-react-app", package_name], TEMP_DIR, log)
            app_dir = os.path.join(TEMP_DIR, package_name)
            log("React app created.")

            src_dir = os.path.join(app_dir, "src")
            public_dir = os.path.join(app_dir, "public")

            log("Step 4: Customizing project files...")
            user_code = self.text_area.get("1.0", tk.END).strip()
            if not user_code:
                raise ValueError("React code cannot be empty.")
            with open(os.path.join(src_dir, "App.js"), "w", encoding="utf-8") as f: f.write(user_code)
            with open(os.path.join(src_dir, "index.js"), "w", encoding="utf-8") as f: f.write(REACT_TEMPLATE)
            with open(os.path.join(public_dir, "electron.js"), "w", encoding="utf-8") as f: f.write(ELECTRON_MAIN)
            with open(os.path.join(public_dir, "preload.js"), "w", encoding="utf-8") as f: f.write("// Preload script")
            
            package_json_content = PACKAGE_JSON.format(app_name=product_name, app_name_lowercase=package_name)
            with open(os.path.join(app_dir, "package.json"), "w", encoding="utf-8") as f: f.write(package_json_content)
            log("Project files customized.")

            log("Step 5: Installing dependencies with 'npm install'...")
            self.run_command_and_stream_output([npm_path, "install"], app_dir, log)
            log("Dependencies installed.")

            log("Step 6: Building React app with 'npm run build'...")
            self.run_command_and_stream_output([npm_path, "run", "build"], app_dir, log)
            log("React app built.")

            log("Step 7: Building Electron app with 'npm run dist'...")
            self.run_command_and_stream_output([npm_path, "run", "dist"], app_dir, log)
            log("Electron app built.")

            log("Step 8: Copying build artifact to Downloads folder...")
            dist_path = os.path.join(app_dir, "dist")
            artifact_found = False
            for file in os.listdir(dist_path):
                if file.endswith((".exe", ".dmg", ".AppImage", ".msi", ".zip")):
                    shutil.copy(os.path.join(dist_path, file), app_output_folder)
                    artifact_found = True
                    log(f"Copied: {file} to {app_output_folder}")
            
            if artifact_found:
                self.build_queue.put(("success", f"Build successful!\nInstaller located in: {app_output_folder}"))
            else:
                self.build_queue.put(("error", "Build finished, but no installer was found in the dist folder."))

        except (Exception, subprocess.CalledProcessError) as e:
            error_message = f"Build failed."
            if isinstance(e, subprocess.CalledProcessError):
                error_message = f"A build step failed ('{' '.join(e.cmd)}'). See log above for details."
            else:
                error_message = f"An unexpected error occurred: {str(e)}"
            
            log(error_message)
            self.build_queue.put(("error", error_message))
        
        finally:
            if app_output_folder:
                log("Finalizing build: saving log file...")
                try:
                    log_file_path = os.path.join(app_output_folder, "build_log.txt")
                    with open(log_file_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(log_messages))
                    log(f"Build log saved to: {log_file_path}")
                except Exception as log_e:
                    log(f"Error: Could not save build log. Reason: {log_e}")
            
            self.build_queue.put(("done", None))

if __name__ == "__main__":
    root = tk.Tk()
    app = ElectronAutoBuildApp(root)
    root.mainloop()
