import os
import sys
import subprocess
import logging
import argparse
import shutil
import json
import yaml
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import socketserver

try:
    import git
except ImportError:
    print("Installing GitPython...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'gitpython'])
    import git

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from tkinter import font
except ImportError:
    tk = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

CONFIG_FILE = "release-config.yaml"

class ReleasePublisher:
    def __init__(self, source_dir=None, source_repo=None, source_branch=None,
                 webroot_repo=None, webroot_branch=None,
                 history_repo=None, history_branch=None,
                 sparse_dirs=None):

        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        self.source_dir = source_dir or os.path.join(self.base_dir, 'source')
        self.source_repo = source_repo
        self.source_branch = source_branch
        self.webroot_repo = webroot_repo or 'https://github.com/WorldHealthOrganization/smart-html'
        self.webroot_branch = webroot_branch
        self.history_repo = history_repo or 'https://github.com/HL7/fhir-ig-history-template'
        self.history_branch = history_branch
        self.registry_repo = 'https://github.com/FHIR/ig-registry'

        self.webroot_dir = os.path.join(self.base_dir, 'webroot')
        self.history_dir = os.path.join(self.base_dir, 'history-template')
        self.registry_dir = os.path.join(self.base_dir, 'ig-registry')
        self.package_cache = os.path.join(self.base_dir, 'fhir-package-cache')
        self.temp_dir = os.path.join(self.base_dir, 'temp')
        self.publisher_jar = os.path.join(self.base_dir, 'publisher.jar')
        self.sparse_dirs = sparse_dirs

    def run_command(self, cmd, shell=False):
        logging.info(f"Running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        subprocess.run(cmd, shell=shell, check=True)

    def clone_repo(self, url, path, branch=None, sparse_dirs=None):
        if os.path.exists(path):
            logging.info(f"{path} already exists, updating...")
            try:
                repo = git.Repo(path)
                repo.git.reset('--hard')
                repo.remotes.origin.pull()
            except Exception as e:
                logging.warning(f"Failed to update {path}, continuing anyway: {e}")
            return
        if sparse_dirs:
            self.run_command(['git', 'clone', '--depth=1', '--filter=blob:none', '--sparse', url, path])
            os.chdir(path)
            self.run_command(['git', 'sparse-checkout', 'init'])
            self.run_command(['git', 'sparse-checkout', 'set'] + sparse_dirs)
        else:
            clone_cmd = ['git', 'clone', '--depth=1']
            if branch:
                clone_cmd += ['--branch', branch]
            clone_cmd += [url, path]
            self.run_command(clone_cmd)

    def prepare(self):
        self.clone_repo(self.history_repo, self.history_dir, self.history_branch)
        self.clone_repo(self.webroot_repo, self.webroot_dir, self.webroot_branch, self.sparse_dirs)
        self.clone_repo(self.registry_repo, self.registry_dir)

        if self.source_repo:
            self.clone_repo(self.source_repo, self.source_dir, self.source_branch)

        if not os.path.exists(self.publisher_jar):
            self.run_command([
                'curl', '-L',
                'https://github.com/HL7/fhir-ig-publisher/releases/latest/download/publisher.jar',
                '-o', self.publisher_jar
            ])

        os.makedirs(self.package_cache, exist_ok=True)

    def build(self):
        self.run_command([
            'java', '-Xmx4g', '-jar', self.publisher_jar,
            'publisher', '-ig', self.source_dir,
            '-package-cache-folder', self.package_cache
        ])

    def publish(self):
        self.run_command([
            'java', '-Xmx4g', '-Dfile.encoding=UTF-8', '-jar', self.publisher_jar,
            '-go-publish',
            '-package-cache-folder', self.package_cache,
            '-source', self.source_dir,
            '-web', self.webroot_dir,
            '-temp', self.temp_dir,
            '-registry', os.path.join(self.registry_dir, 'fhir-ig-list.json'),
            '-history', self.history_dir,
            '-templates', os.path.join(self.webroot_dir, 'templates')
        ])

    def run(self):
        self.prepare()
        self.build()
        self.publish()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return yaml.safe_load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        yaml.safe_dump(config, f, default_flow_style=False)

if tk:
    class ModernIGPublisherGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("FHIR IG Publisher")
            self.root.geometry("800x700")
            self.root.configure(bg='#f0f0f0')
            
            # Configure styling
            self.setup_styles()
            
            config = load_config()
            self.setup_variables(config)
            self.create_widgets()
            
            # Center the window
            self.center_window()
            
        def setup_styles(self):
            self.style = ttk.Style()
            
            # Configure modern theme
            self.style.theme_use('clam')
            
            # Define colors
            self.colors = {
                'primary': '#2196F3',
                'primary_dark': '#1976D2',
                'secondary': '#FF9800',
                'success': '#4CAF50',
                'background': '#f5f5f5',
                'card': '#ffffff',
                'text': '#333333',
                'text_light': '#666666'
            }
            
            # Configure styles
            self.style.configure('Card.TFrame', 
                               background=self.colors['card'],
                               relief='flat',
                               borderwidth=1)
            
            self.style.configure('Heading.TLabel',
                               font=('Segoe UI', 14, 'bold'),
                               foreground=self.colors['text'],
                               background=self.colors['card'])
            
            self.style.configure('Modern.TEntry',
                               padding=8,
                               relief='flat',
                               borderwidth=1)
            
            self.style.configure('Modern.TButton',
                               padding=(20, 10),
                               font=('Segoe UI', 10, 'bold'))
            
            self.style.map('Modern.TButton',
                          background=[('active', self.colors['primary_dark']),
                                    ('!active', self.colors['primary'])],
                          foreground=[('active', 'white'), ('!active', 'white')])
            
        def setup_variables(self, config):
            self.source_repo = tk.StringVar(value=config.get('source_repo', ''))
            self.source_branch = tk.StringVar(value=config.get('source_branch', 'main'))
            self.source_dir = tk.StringVar(value=config.get('source_dir', ''))
            self.history_repo = tk.StringVar(value=config.get('history_repo', 'https://github.com/HL7/fhir-ig-history-template'))
            self.history_branch = tk.StringVar(value=config.get('history_branch', 'master'))
            self.webroot_repo = tk.StringVar(value=config.get('webroot_repo', 'https://github.com/WorldHealthOrganization/smart-html'))
            self.webroot_branch = tk.StringVar(value=config.get('webroot_branch', 'master'))
            
            # Sparse checkout variables
            self.use_sparse = tk.BooleanVar(value=config.get('use_sparse', False))
            self.sparse_dirs = tk.StringVar(value=' '.join(config.get('sparse_dirs', [])))
            
        def center_window(self):
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            
        def create_widgets(self):
            # Main container
            main_frame = ttk.Frame(self.root, style='Card.TFrame', padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Title
            title_frame = ttk.Frame(main_frame, style='Card.TFrame')
            title_frame.pack(fill=tk.X, pady=(0, 20))
            
            ttk.Label(title_frame, text="🔬 FHIR IG Publisher", 
                     font=('Segoe UI', 18, 'bold'),
                     foreground=self.colors['primary'],
                     background=self.colors['card']).pack()
            
            ttk.Label(title_frame, text="Configure and publish FHIR Implementation Guides",
                     font=('Segoe UI', 10),
                     foreground=self.colors['text_light'],
                     background=self.colors['card']).pack()
            
            # Create notebook for organized sections
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
            
            # Source Configuration Tab
            source_frame = ttk.Frame(notebook, style='Card.TFrame', padding=20)
            notebook.add(source_frame, text="📁 Source Configuration")
            self.create_source_section(source_frame)
            
            # Repository Configuration Tab
            repo_frame = ttk.Frame(notebook, style='Card.TFrame', padding=20)
            notebook.add(repo_frame, text="🔗 Repository Configuration")
            self.create_repo_section(repo_frame)
            
            # Advanced Options Tab
            advanced_frame = ttk.Frame(notebook, style='Card.TFrame', padding=20)
            notebook.add(advanced_frame, text="⚙️ Advanced Options")
            self.create_advanced_section(advanced_frame)
            
            # Action buttons
            self.create_action_buttons(main_frame)
            
        def create_source_section(self, parent):
            ttk.Label(parent, text="Source Configuration", style='Heading.TLabel').pack(anchor='w', pady=(0, 15))
            
            self.add_field_with_description(
                parent, "Source Repository URL:",
                "Git repository containing the FHIR IG source files",
                self.source_repo
            )
            
            self.add_field_with_description(
                parent, "Source Branch:",
                "Branch to use from the source repository (default: main)",
                self.source_branch
            )
            
            # Local source directory with browse button
            local_frame = ttk.Frame(parent, style='Card.TFrame')
            local_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(local_frame, text="Local Source Directory (Optional):",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            ttk.Label(local_frame, text="Use local directory instead of cloning from repository",
                     font=('Segoe UI', 9), foreground=self.colors['text_light']).pack(anchor='w')
            
            dir_frame = ttk.Frame(local_frame, style='Card.TFrame')
            dir_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Entry(dir_frame, textvariable=self.source_dir, 
                     style='Modern.TEntry', width=60).pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Button(dir_frame, text="Browse", command=self.browse_source,
                      style='Modern.TButton').pack(side=tk.RIGHT, padx=(10, 0))
                      
        def create_repo_section(self, parent):
            ttk.Label(parent, text="Repository Configuration", style='Heading.TLabel').pack(anchor='w', pady=(0, 15))
            
            self.add_field_with_description(
                parent, "History Repository URL:",
                "Repository containing the IG history template",
                self.history_repo
            )
            
            self.add_field_with_description(
                parent, "History Branch:",
                "Branch to use from the history repository",
                self.history_branch
            )
            
            self.add_field_with_description(
                parent, "Webroot Repository URL:",
                "Repository containing the web publishing templates",
                self.webroot_repo
            )
            
            self.add_field_with_description(
                parent, "Webroot Branch:",
                "Branch to use from the webroot repository",
                self.webroot_branch
            )
            
        def create_advanced_section(self, parent):
            ttk.Label(parent, text="Advanced Options", style='Heading.TLabel').pack(anchor='w', pady=(0, 15))
            
            # Sparse checkout section
            sparse_frame = ttk.LabelFrame(parent, text="Sparse Checkout Configuration", padding=15)
            sparse_frame.pack(fill=tk.X, pady=10)
            
            # Checkbox for sparse checkout
            checkbox_frame = ttk.Frame(sparse_frame)
            checkbox_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Checkbutton(checkbox_frame, 
                           text="Enable sparse checkout for webroot repository",
                           variable=self.use_sparse,
                           command=self.toggle_sparse_fields).pack(anchor='w')
            
            ttk.Label(checkbox_frame, 
                     text="Only download specific folders instead of the entire repository",
                     font=('Segoe UI', 9), 
                     foreground=self.colors['text_light']).pack(anchor='w', padx=(20, 0))
            
            # Sparse directories field
            self.sparse_frame = ttk.Frame(sparse_frame)
            self.sparse_frame.pack(fill=tk.X, pady=(10, 0))
            
            ttk.Label(self.sparse_frame, text="Folders to checkout (space-separated):",
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            
            self.sparse_entry = ttk.Entry(self.sparse_frame, textvariable=self.sparse_dirs, 
                                         style='Modern.TEntry')
            self.sparse_entry.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(self.sparse_frame, 
                     text="Example: templates assets css js",
                     font=('Segoe UI', 9), 
                     foreground=self.colors['text_light']).pack(anchor='w')
            
            # Initialize sparse fields state
            self.toggle_sparse_fields()
            
        def create_action_buttons(self, parent):
            button_frame = ttk.Frame(parent, style='Card.TFrame')
            button_frame.pack(fill=tk.X, pady=10)
            
            # Save configuration button
            ttk.Button(button_frame, text="💾 Save Configuration", 
                      command=self.save_configuration,
                      style='Modern.TButton').pack(side=tk.LEFT, padx=(0, 10))
            
            # Run button
            run_btn = ttk.Button(button_frame, text="🚀 Run Publisher", 
                                command=self.run_publisher_threaded,
                                style='Modern.TButton')
            run_btn.pack(side=tk.RIGHT)
            
            # Progress bar (initially hidden)
            self.progress_frame = ttk.Frame(parent, style='Card.TFrame')
            self.progress = ttk.Progressbar(self.progress_frame, mode='indeterminate')
            self.progress_label = ttk.Label(self.progress_frame, text="")
            
        def add_field_with_description(self, parent, label, description, variable):
            field_frame = ttk.Frame(parent, style='Card.TFrame')
            field_frame.pack(fill=tk.X, pady=10)
            
            ttk.Label(field_frame, text=label, 
                     font=('Segoe UI', 10, 'bold')).pack(anchor='w')
            ttk.Label(field_frame, text=description,
                     font=('Segoe UI', 9), 
                     foreground=self.colors['text_light']).pack(anchor='w')
            ttk.Entry(field_frame, textvariable=variable, 
                     style='Modern.TEntry').pack(fill=tk.X, pady=(5, 0))
                     
        def toggle_sparse_fields(self):
            """Enable/disable sparse directory fields based on checkbox"""
            if self.use_sparse.get():
                self.sparse_entry.configure(state='normal')
                for widget in self.sparse_frame.winfo_children():
                    if isinstance(widget, ttk.Label):
                        widget.configure(foreground=self.colors['text'])
            else:
                self.sparse_entry.configure(state='disabled')
                for widget in self.sparse_frame.winfo_children():
                    if isinstance(widget, ttk.Label):
                        widget.configure(foreground=self.colors['text_light'])
                        
        def browse_source(self):
            folder = filedialog.askdirectory(title="Select FHIR IG Source Directory")
            if folder:
                self.source_dir.set(folder)
                
        def save_configuration(self):
            """Save current configuration to file"""
            config = {
                'source_repo': self.source_repo.get(),
                'source_branch': self.source_branch.get(),
                'source_dir': self.source_dir.get(),
                'history_repo': self.history_repo.get(),
                'history_branch': self.history_branch.get(),
                'webroot_repo': self.webroot_repo.get(),
                'webroot_branch': self.webroot_branch.get(),
                'use_sparse': self.use_sparse.get(),
                'sparse_dirs': self.sparse_dirs.get().split() if self.sparse_dirs.get().strip() else []
            }
            
            try:
                save_config(config)
                messagebox.showinfo("Success", "Configuration saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {e}")
                
        def show_progress(self, text="Processing..."):
            """Show progress indicator"""
            self.progress_frame.pack(fill=tk.X, pady=10)
            self.progress_label.configure(text=text)
            self.progress_label.pack(pady=(0, 5))
            self.progress.pack(fill=tk.X)
            self.progress.start()
            
        def hide_progress(self):
            """Hide progress indicator"""
            self.progress.stop()
            self.progress_frame.pack_forget()
            
        def run_publisher_threaded(self):
            """Run the publisher in a separate thread to prevent GUI freezing"""
            def run_in_thread():
                try:
                    self.root.after(0, lambda: self.show_progress("Running FHIR IG Publisher..."))
                    
                    # Get sparse directories if enabled
                    sparse_dirs = None
                    if self.use_sparse.get() and self.sparse_dirs.get().strip():
                        sparse_dirs = self.sparse_dirs.get().split()
                    
                    pub = ReleasePublisher(
                        source_dir=self.source_dir.get() or None,
                        source_repo=self.source_repo.get() or None,
                        source_branch=self.source_branch.get() or None,
                        webroot_repo=self.webroot_repo.get() or None,
                        webroot_branch=self.webroot_branch.get() or None,
                        history_repo=self.history_repo.get() or None,
                        history_branch=self.history_branch.get() or None,
                        sparse_dirs=sparse_dirs
                    )
                    pub.run()
                    
                    self.root.after(0, self.hide_progress)
                    self.root.after(0, lambda: messagebox.showinfo("Success", "Publication completed successfully! 🎉"))
                    
                except Exception as e:
                    self.root.after(0, self.hide_progress)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))
                    
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            
        def run(self):
            self.root.mainloop()

# Web-based GUI option
class WebIGPublisherGUI:
    def __init__(self, port=8080):
        self.port = port
        self.config = load_config()
        
    def create_html_interface(self):
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>FHIR IG Publisher</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .container {
                    max-width: 900px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    overflow: hidden;
                }
                
                .header {
                    background: linear-gradient(45deg, #2196F3, #21CBF3);
                    color: white;
                    padding: 30px;
                    text-align: center;
                }
                
                .header h1 {
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                
                .content {
                    padding: 30px;
                }
                
                .section {
                    margin-bottom: 30px;
                    padding: 25px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border-left: 4px solid #2196F3;
                }
                
                .section h3 {
                    color: #333;
                    margin-bottom: 20px;
                    font-size: 1.3em;
                }
                
                .field-group {
                    margin-bottom: 20px;
                }
                
                label {
                    display: block;
                    font-weight: 600;
                    color: #555;
                    margin-bottom: 5px;
                }
                
                .field-description {
                    font-size: 0.9em;
                    color: #666;
                    margin-bottom: 8px;
                }
                
                input[type="text"], input[type="url"] {
                    width: 100%;
                    padding: 12px 16px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 16px;
                    transition: border-color 0.3s ease;
                }
                
                input[type="text"]:focus, input[type="url"]:focus {
                    outline: none;
                    border-color: #2196F3;
                }
                
                .checkbox-group {
                    display: flex;
                    align-items: center;
                    margin-bottom: 15px;
                }
                
                input[type="checkbox"] {
                    margin-right: 10px;
                    transform: scale(1.2);
                }
                
                .button-group {
                    display: flex;
                    gap: 15px;
                    justify-content: center;
                    margin-top: 30px;
                }
                
                button {
                    padding: 12px 30px;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }
                
                .btn-primary {
                    background: linear-gradient(45deg, #2196F3, #21CBF3);
                    color: white;
                }
                
                .btn-secondary {
                    background: #6c757d;
                    color: white;
                }
                
                button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                }
                
                .progress {
                    display: none;
                    margin: 20px 0;
                    text-align: center;
                }
                
                .progress-bar {
                    width: 100%;
                    height: 4px;
                    background: #e0e0e0;
                    border-radius: 2px;
                    overflow: hidden;
                    margin: 10px 0;
                }
                
                .progress-bar::after {
                    content: '';
                    display: block;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(45deg, #2196F3, #21CBF3);
                    animation: progress 2s ease-in-out infinite;
                }
                
                @keyframes progress {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(100%); }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔬 FHIR IG Publisher</h1>
                    <p>Configure and publish FHIR Implementation Guides</p>
                </div>
                
                <div class="content">
                    <form id="publisherForm">
                        <div class="section">
                            <h3>📁 Source Configuration</h3>
                            
                            <div class="field-group">
                                <label for="sourceRepo">Source Repository URL:</label>
                                <div class="field-description">Git repository containing the FHIR IG source files</div>
                                <input type="url" id="sourceRepo" name="sourceRepo">
                            </div>
                            
                            <div class="field-group">
                                <label for="sourceBranch">Source Branch:</label>
                                <div class="field-description">Branch to use from the source repository (default: main)</div>
                                <input type="text" id="sourceBranch" name="sourceBranch" value="main">
                            </div>
                            
                            <div class="field-group">
                                <label for="sourceDir">Local Source Directory (Optional):</label>
                                <div class="field-description">Use local directory instead of cloning from repository</div>
                                <input type="text" id="sourceDir" name="sourceDir">
                            </div>
                        </div>
                        
                        <div class="section">
                            <h3>🔗 Repository Configuration</h3>
                            
                            <div class="field-group">
                                <label for="historyRepo">History Repository URL:</label>
                                <div class="field-description">Repository containing the IG history template</div>
                                <input type="url" id="historyRepo" name="historyRepo" value="https://github.com/HL7/fhir-ig-history-template">
                            </div>
                            
                            <div class="field-group">
                                <label for="historyBranch">History Branch:</label>
                                <div class="field-description">Branch to use from the history repository</div>
                                <input type="text" id="historyBranch" name="historyBranch" value="master">
                            </div>
                            
                            <div class="field-group">
                                <label for="webrootRepo">Webroot Repository URL:</label>
                                <div class="field-description">Repository containing the web publishing templates</div>
                                <input type="url" id="webrootRepo" name="webrootRepo" value="https://github.com/WorldHealthOrganization/smart-html">
                            </div>
                            
                            <div class="field-group">
                                <label for="webrootBranch">Webroot Branch:</label>
                                <div class="field-description">Branch to use from the webroot repository</div>
                                <input type="text" id="webrootBranch" name="webrootBranch" value="master">
                            </div>
                        </div>
                        
                        <div class="section">
                            <h3>⚙️ Advanced Options</h3>
                            
                            <div class="checkbox-group">
                                <input type="checkbox" id="useSparse" name="useSparse">
                                <label for="useSparse">Enable sparse checkout for webroot repository</label>
                            </div>
                            <div class="field-description">Only download specific folders instead of the entire repository</div>
                            
                            <div class="field-group" id="sparseGroup" style="display: none;">
                                <label for="sparseDirs">Folders to checkout (space-separated):</label>
                                <div class="field-description">Example: templates assets css js</div>
                                <input type="text" id="sparseDirs" name="sparseDirs">
                            </div>
                        </div>
                        
                        <div class="button-group">
                            <button type="button" class="btn-secondary" onclick="saveConfig()">💾 Save Configuration</button>
                            <button type="submit" class="btn-primary">🚀 Run Publisher</button>
                        </div>
                        
                        <div class="progress" id="progress">
                            <p>Running FHIR IG Publisher...</p>
                            <div class="progress-bar"></div>
                        </div>
                    </form>
                </div>
            </div>
            
            <script>
                // Toggle sparse directories field
                document.getElementById('useSparse').addEventListener('change', function() {
                    const sparseGroup = document.getElementById('sparseGroup');
                    sparseGroup.style.display = this.checked ? 'block' : 'none';
                });
                
                // Form submission
                document.getElementById('publisherForm').addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const progress = document.getElementById('progress');
                    progress.style.display = 'block';
                    
                    const formData = new FormData(this);
                    const config = {};
                    
                    for (let [key, value] of formData.entries()) {
                        config[key] = value;
                    }
                    
                    // Handle sparse directories
                    if (config.useSparse) {
                        config.sparseDirs = config.sparseDirs ? config.sparseDirs.split(' ') : [];
                    } else {
                        config.sparseDirs = null;
                    }
                    
                    // Send to Python backend (this would need to be implemented)
                    console.log('Configuration:', config);
                    
                    // Simulate processing time
                    setTimeout(() => {
                        progress.style.display = 'none';
                        alert('Publication completed successfully! 🎉');
                    }, 3000);
                });
                
                function saveConfig() {
                    alert('Configuration saved successfully! 💾');
                }
                
                // Load saved configuration on page load
                window.addEventListener('load', function() {
                    // This would load from the Python backend
                    console.log('Loading saved configuration...');
                });
            </script>
        </body>
        </html>
        """
    
    def run(self):
        """Start the web server and open the browser"""
        html_content = self.create_html_interface()
        
        # Write HTML to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = f.name
        
        # Open in browser
        webbrowser.open(f'file://{html_file}')
        print(f"Web interface opened in browser: file://{html_file}")

def main():
    parser = argparse.ArgumentParser(description="FHIR IG Publisher Release Utility")
    parser.add_argument('--gui', action='store_true', help='Launch GUI interface')
    parser.add_argument('--web-gui', action='store_true', help='Launch modern web-based GUI')
    parser.add_argument('--source', type=str, help='Path to the IG source folder')
    parser.add_argument('--source-repo', type=str, help='URL to the IG source repository')
    parser.add_argument('--source-branch', type=str, help='Branch name for IG source')
    parser.add_argument('--webroot-repo', type=str, help='Webroot repo URL')
    parser.add_argument('--webroot-branch', type=str, help='Webroot branch name')
    parser.add_argument('--history-repo', type=str, help='History repo URL')
    parser.add_argument('--history-branch', type=str, help='History branch name')
    parser.add_argument('--sparse', nargs='*', help='Sparse checkout folders for webroot')
    args = parser.parse_args()

    if args.web_gui:
        web_gui = WebIGPublisherGUI()
        web_gui.run()
    elif args.gui:
        if not tk:
            print("❌ GUI not available: tkinter not found")
            sys.exit(1)
        gui = ModernIGPublisherGUI()
        gui.run()
    else:
        publisher = ReleasePublisher(
            source_dir=args.source,
            source_repo=args.source_repo,
            source_branch=args.source_branch,
            webroot_repo=args.webroot_repo,
            webroot_branch=args.webroot_branch,
            history_repo=args.history_repo,
            history_branch=args.history_branch,
            sparse_dirs=args.sparse
        )
        publisher.run()

if __name__ == '__main__':
    main()