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
                 sparse_dirs=None, enable_sparse_checkout=False):

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
        
        # Updated sparse checkout logic
        self.sparse_dirs = sparse_dirs
        self.enable_sparse_checkout = enable_sparse_checkout

    def run_command(self, cmd, shell=False):
        logging.info(f"Running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        subprocess.run(cmd, shell=shell, check=True)

    def clone_repo(self, url, path, branch=None, use_sparse=False, sparse_dirs=None):
        if os.path.exists(path):
            logging.info(f"{path} already exists, updating...")
            try:
                repo = git.Repo(path)
                repo.git.reset('--hard')
                repo.remotes.origin.pull()
            except Exception as e:
                logging.warning(f"Failed to update {path}, continuing anyway: {e}")
            return
            
        # Use sparse checkout only if explicitly enabled AND sparse_dirs provided
        if use_sparse and sparse_dirs:
            self.run_command(['git', 'clone', '--depth=1', '--filter=blob:none', '--sparse', url, path])
            original_cwd = os.getcwd()
            os.chdir(path)
            try:
                self.run_command(['git', 'sparse-checkout', 'init'])
                self.run_command(['git', 'sparse-checkout', 'set'] + sparse_dirs)
            finally:
                os.chdir(original_cwd)
        else:
            clone_cmd = ['git', 'clone', '--depth=1']
            if branch:
                clone_cmd += ['--branch', branch]
            clone_cmd += [url, path]
            self.run_command(clone_cmd)

    def prepare(self):
        self.clone_repo(self.history_repo, self.history_dir, self.history_branch)
        
        # Only use sparse checkout for webroot if explicitly enabled
        self.clone_repo(
            self.webroot_repo, 
            self.webroot_dir, 
            self.webroot_branch, 
            use_sparse=self.enable_sparse_checkout,
            sparse_dirs=self.sparse_dirs
        )
        
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
    class BeautifulIGPublisherGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("FHIR IG Publisher")
            self.root.geometry("1000x800")
            
            # Set beautiful gradient background
            self.setup_styles()
            
            config = load_config()
            self.setup_variables(config)
            self.create_widgets()
            
            # Center the window
            self.center_window()
            
        def setup_styles(self):
            """Setup beautiful modern theme"""
            self.style = ttk.Style()
            self.style.theme_use('clam')
            
            # Beautiful color palette
            self.colors = {
                'primary': '#6C63FF',      # Beautiful purple
                'primary_dark': '#5A52D5',
                'primary_light': '#8B82FF',
                'secondary': '#FF6B9D',    # Pink accent
                'success': '#00D4AA',      # Teal green
                'warning': '#FFB800',      # Orange
                'background': '#F8F9FF',   # Very light purple
                'card': '#FFFFFF',
                'card_elevated': '#FFFFFF',
                'text': '#2D3748',
                'text_light': '#718096',
                'text_muted': '#A0AEC0',
                'border': '#E2E8F0',
                'shadow': '#00000010'
            }
            
            # Configure root window
            self.root.configure(bg=self.colors['background'])
            
            # Main card frame style
            self.style.configure('Card.TFrame', 
                               background=self.colors['card'],
                               relief='flat',
                               borderwidth=0)
            
            # Elevated card style
            self.style.configure('Elevated.TFrame',
                               background=self.colors['card_elevated'],
                               relief='solid',
                               borderwidth=1,
                               bordercolor=self.colors['border'])
            
            # Headers
            self.style.configure('Title.TLabel',
                               font=('Segoe UI', 24, 'bold'),
                               foreground=self.colors['primary'],
                               background=self.colors['card'])
            
            self.style.configure('Subtitle.TLabel',
                               font=('Segoe UI', 11),
                               foreground=self.colors['text_light'],
                               background=self.colors['card'])
            
            self.style.configure('SectionHeader.TLabel',
                               font=('Segoe UI', 16, 'bold'),
                               foreground=self.colors['text'],
                               background=self.colors['card'])
            
            self.style.configure('FieldLabel.TLabel',
                               font=('Segoe UI', 10, 'bold'),
                               foreground=self.colors['text'],
                               background=self.colors['card'])
            
            self.style.configure('FieldDesc.TLabel',
                               font=('Segoe UI', 9),
                               foreground=self.colors['text_muted'],
                               background=self.colors['card'])
            
            # Modern entries
            self.style.configure('Modern.TEntry',
                               fieldbackground='white',
                               bordercolor=self.colors['border'],
                               lightcolor=self.colors['border'],
                               darkcolor=self.colors['border'],
                               focuscolor=self.colors['primary'],
                               borderwidth=2,
                               padding=(12, 8))
            
            self.style.map('Modern.TEntry',
                          focuscolor=[('!focus', self.colors['border']),
                                    ('focus', self.colors['primary'])],
                          bordercolor=[('focus', self.colors['primary'])])
            
            # Beautiful buttons
            self.style.configure('Primary.TButton',
                               font=('Segoe UI', 11, 'bold'),
                               foreground='white',
                               borderwidth=0,
                               focuscolor='none',
                               padding=(25, 12))
            
            self.style.map('Primary.TButton',
                          background=[('active', self.colors['primary_dark']),
                                    ('pressed', self.colors['primary_dark']),
                                    ('!active', self.colors['primary'])],
                          relief=[('pressed', 'flat'),
                                ('!pressed', 'flat')])
            
            self.style.configure('Secondary.TButton',
                               font=('Segoe UI', 10, 'bold'),
                               foreground=self.colors['text'],
                               borderwidth=2,
                               bordercolor=self.colors['border'],
                               focuscolor='none',
                               padding=(20, 10))
            
            self.style.map('Secondary.TButton',
                          background=[('active', self.colors['background']),
                                    ('!active', 'white')],
                          bordercolor=[('active', self.colors['primary']),
                                     ('!active', self.colors['border'])])
            
            # Modern checkbutton
            self.style.configure('Modern.TCheckbutton',
                               font=('Segoe UI', 10, 'bold'),
                               foreground=self.colors['text'],
                               background=self.colors['card'],
                               focuscolor='none')
            
            # Beautiful notebook
            self.style.configure('Beautiful.TNotebook',
                               background=self.colors['card'],
                               borderwidth=0,
                               tabmargins=0)
            
            self.style.configure('Beautiful.TNotebook.Tab',
                               padding=(20, 15),
                               font=('Segoe UI', 10, 'bold'),
                               background=self.colors['background'],
                               foreground=self.colors['text_light'],
                               borderwidth=0)
            
            self.style.map('Beautiful.TNotebook.Tab',
                          background=[('selected', self.colors['card']),
                                    ('!selected', self.colors['background'])],
                          foreground=[('selected', self.colors['primary']),
                                    ('!selected', self.colors['text_light'])])
            
        def setup_variables(self, config):
            # Set defaults from your config
            self.source_repo = tk.StringVar(value=config.get('source_repo', 'https://github.com/WorldHealthOrganization/smart-dak-pnc'))
            self.source_branch = tk.StringVar(value=config.get('source_branch', 'v0.9.9_releaseCandidate'))
            self.source_dir = tk.StringVar(value=config.get('source_dir', ''))
            self.history_repo = tk.StringVar(value=config.get('history_repo', 'https://github.com/HL7/fhir-ig-history-template'))
            self.history_branch = tk.StringVar(value=config.get('history_branch', 'main'))
            self.webroot_repo = tk.StringVar(value=config.get('webroot_repo', 'https://github.com/WorldHealthOrganization/smart-html'))
            self.webroot_branch = tk.StringVar(value=config.get('webroot_branch', 'main'))
            
            # Sparse checkout with boolean option
            self.enable_sparse_checkout = tk.BooleanVar(value=config.get('enable_sparse_checkout', False))
            self.sparse_dirs = tk.StringVar(value=' '.join(config.get('sparse_dirs', ['templates', 'assets'])))
            
        def center_window(self):
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            
        def create_widgets(self):
            # Main container with padding
            main_container = tk.Frame(self.root, bg=self.colors['background'])
            main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Header card
            header_card = ttk.Frame(main_container, style='Card.TFrame', padding=40)
            header_card.pack(fill=tk.X, pady=(0, 20))
            
            # Add shadow effect by creating a slightly offset frame
            shadow_frame = tk.Frame(main_container, bg='#000008', height=2)
            shadow_frame.pack(fill=tk.X, pady=(0, 18))
            
            # Beautiful header with icon
            header_frame = ttk.Frame(header_card, style='Card.TFrame')
            header_frame.pack(fill=tk.X)
            
            title_frame = ttk.Frame(header_frame, style='Card.TFrame')
            title_frame.pack()
            
            ttk.Label(title_frame, text="🧬", 
                     font=('Segoe UI', 32),
                     background=self.colors['card']).pack(side=tk.LEFT, padx=(0, 15))
            
            text_frame = ttk.Frame(title_frame, style='Card.TFrame')
            text_frame.pack(side=tk.LEFT)
            
            ttk.Label(text_frame, text="FHIR IG Publisher", 
                     style='Title.TLabel').pack(anchor='w')
            ttk.Label(text_frame, text="Beautiful interface for configuring and publishing FHIR Implementation Guides",
                     style='Subtitle.TLabel').pack(anchor='w')
            
            # Main content card
            content_card = ttk.Frame(main_container, style='Card.TFrame', padding=30)
            content_card.pack(fill=tk.BOTH, expand=True)
            
            # Beautiful notebook with icons
            notebook = ttk.Notebook(content_card, style='Beautiful.TNotebook')
            notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 25))
            
            # Source Configuration Tab
            source_frame = ttk.Frame(notebook, style='Card.TFrame', padding=30)
            notebook.add(source_frame, text="📂  Source Configuration")
            self.create_source_section(source_frame)
            
            # Repository Configuration Tab
            repo_frame = ttk.Frame(notebook, style='Card.TFrame', padding=30)
            notebook.add(repo_frame, text="🔗  Repository Settings")
            self.create_repo_section(repo_frame)
            
            # Advanced Options Tab
            advanced_frame = ttk.Frame(notebook, style='Card.TFrame', padding=30)
            notebook.add(advanced_frame, text="⚡  Advanced Options")
            self.create_advanced_section(advanced_frame)
            
            # Beautiful action buttons
            self.create_action_buttons(content_card)
            
        def create_source_section(self, parent):
            ttk.Label(parent, text="Source Configuration", style='SectionHeader.TLabel').pack(anchor='w', pady=(0, 25))
            
            self.add_beautiful_field(
                parent, "Source Repository URL",
                "Git repository containing your FHIR IG source files",
                self.source_repo, "🌐"
            )
            
            self.add_beautiful_field(
                parent, "Source Branch",
                "Specific branch or tag to use from the source repository",
                self.source_branch, "🔀"
            )
            
            # Local source directory with beautiful browse button
            self.create_directory_field(parent)
                      
        def create_repo_section(self, parent):
            ttk.Label(parent, text="Repository Configuration", style='SectionHeader.TLabel').pack(anchor='w', pady=(0, 25))
            
            self.add_beautiful_field(
                parent, "History Repository URL",
                "Repository containing the IG history template for version management",
                self.history_repo, "📚"
            )
            
            self.add_beautiful_field(
                parent, "History Branch",
                "Branch to use from the history repository",
                self.history_branch, "🌿"
            )
            
            self.add_beautiful_field(
                parent, "Webroot Repository URL",
                "Repository containing web publishing templates and assets",
                self.webroot_repo, "🌍"
            )
            
            self.add_beautiful_field(
                parent, "Webroot Branch",
                "Branch to use from the webroot repository",
                self.webroot_branch, "🌳"
            )
            
        def create_advanced_section(self, parent):
            ttk.Label(parent, text="Advanced Configuration", style='SectionHeader.TLabel').pack(anchor='w', pady=(0, 25))
            
            # Beautiful sparse checkout card
            sparse_card = ttk.Frame(parent, style='Elevated.TFrame', padding=25)
            sparse_card.pack(fill=tk.X, pady=(0, 20))
            
            # Card header
            card_header = ttk.Frame(sparse_card, style='Elevated.TFrame')
            card_header.pack(fill=tk.X, pady=(0, 20))
            
            ttk.Label(card_header, text="⚡ Sparse Checkout Optimization", 
                     font=('Segoe UI', 14, 'bold'),
                     foreground=self.colors['primary'],
                     background=self.colors['card']).pack(anchor='w')
            
            ttk.Label(card_header, text="Optimize clone performance by downloading only specific folders",
                     style='FieldDesc.TLabel').pack(anchor='w')
            
            # Checkbox
            checkbox_frame = ttk.Frame(sparse_card, style='Elevated.TFrame')
            checkbox_frame.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Checkbutton(checkbox_frame, 
                           text="Enable sparse checkout for webroot repository",
                           variable=self.enable_sparse_checkout,
                           style='Modern.TCheckbutton',
                           command=self.toggle_sparse_fields).pack(anchor='w')
            
            # Sparse directories field
            self.sparse_frame = ttk.Frame(sparse_card, style='Elevated.TFrame')
            self.sparse_frame.pack(fill=tk.X)
            
            ttk.Label(self.sparse_frame, text="📁 Folders to Download", 
                     style='FieldLabel.TLabel').pack(anchor='w')
            ttk.Label(self.sparse_frame, text="Space-separated list of directories to include",
                     style='FieldDesc.TLabel').pack(anchor='w', pady=(0, 8))
            
            self.sparse_entry = ttk.Entry(self.sparse_frame, textvariable=self.sparse_dirs, 
                                         style='Modern.TEntry', font=('Consolas', 10))
            self.sparse_entry.pack(fill=tk.X)
            
            example_frame = ttk.Frame(self.sparse_frame, style='Elevated.TFrame')
            example_frame.pack(fill=tk.X, pady=(8, 0))
            
            ttk.Label(example_frame, text="💡 Example:", 
                     font=('Segoe UI', 9, 'bold'),
                     foreground=self.colors['secondary'],
                     background=self.colors['card']).pack(side=tk.LEFT)
            ttk.Label(example_frame, text="templates assets css js images",
                     font=('Consolas', 9),
                     foreground=self.colors['text_light'],
                     background=self.colors['card']).pack(side=tk.LEFT, padx=(5, 0))
            
            # Initialize sparse fields state
            self.toggle_sparse_fields()
            
        def create_directory_field(self, parent):
            """Create beautiful directory selection field"""
            dir_card = ttk.Frame(parent, style='Elevated.TFrame', padding=20)
            dir_card.pack(fill=tk.X, pady=15)
            
            ttk.Label(dir_card, text="📁 Local Source Directory", 
                     style='FieldLabel.TLabel').pack(anchor='w')
            ttk.Label(dir_card, text="Optional: Use existing local directory instead of cloning from repository",
                     style='FieldDesc.TLabel').pack(anchor='w', pady=(0, 10))
            
            dir_frame = ttk.Frame(dir_card, style='Elevated.TFrame')
            dir_frame.pack(fill=tk.X)
            
            self.source_entry = ttk.Entry(dir_frame, textvariable=self.source_dir, 
                                         style='Modern.TEntry')
            self.source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            
            browse_btn = ttk.Button(dir_frame, text="🔍 Browse", 
                                  command=self.browse_source,
                                  style='Secondary.TButton')
            browse_btn.pack(side=tk.RIGHT)
            
        def create_action_buttons(self, parent):
            """Create beautiful action buttons"""
            button_frame = ttk.Frame(parent, style='Card.TFrame')
            button_frame.pack(fill=tk.X, pady=20)
            
            # Left side - Save button
            left_frame = ttk.Frame(button_frame, style='Card.TFrame')
            left_frame.pack(side=tk.LEFT)
            
            save_btn = ttk.Button(left_frame, text="💾 Save Configuration", 
                                 command=self.save_configuration,
                                 style='Secondary.TButton')
            save_btn.pack()
            
            # Right side - Run button
            right_frame = ttk.Frame(button_frame, style='Card.TFrame')
            right_frame.pack(side=tk.RIGHT)
            
            run_btn = ttk.Button(right_frame, text="🚀 Run Publisher", 
                               command=self.run_publisher_threaded,
                               style='Primary.TButton')
            run_btn.pack()
            
            # Progress section (initially hidden)
            self.progress_frame = ttk.Frame(parent, style='Card.TFrame')
            
            self.progress_label = ttk.Label(self.progress_frame, text="",
                                          font=('Segoe UI', 10, 'bold'),
                                          foreground=self.colors['primary'])
            
            self.progress = ttk.Progressbar(self.progress_frame, mode='indeterminate',
                                          style='Beautiful.Horizontal.TProgressbar')
            
        def add_beautiful_field(self, parent, label, description, variable, icon="📝"):
            """Add a beautifully styled field with icon"""
            field_card = ttk.Frame(parent, style='Elevated.TFrame', padding=20)
            field_card.pack(fill=tk.X, pady=15)
            
            # Header with icon
            header_frame = ttk.Frame(field_card, style='Elevated.TFrame')
            header_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(header_frame, text=f"{icon} {label}", 
                     style='FieldLabel.TLabel').pack(anchor='w')
            ttk.Label(header_frame, text=description,
                     style='FieldDesc.TLabel').pack(anchor='w')
            
            # Entry field
            entry = ttk.Entry(field_card, textvariable=variable, 
                             style='Modern.TEntry', font=('Segoe UI', 10))
            entry.pack(fill=tk.X)
                     
        def toggle_sparse_fields(self):
            """Enable/disable sparse directory fields based on checkbox"""
            if self.enable_sparse_checkout.get():
                self.sparse_entry.configure(state='normal')
                # Update label colors to active
                for widget in self.sparse_frame.winfo_children():
                    if isinstance(widget, ttk.Label):
                        widget.configure(foreground=self.colors['text'])
            else:
                self.sparse_entry.configure(state='disabled')
                # Update label colors to muted
                for widget in self.sparse_frame.winfo_children():
                    if isinstance(widget, ttk.Label):
                        widget.configure(foreground=self.colors['text_muted'])
                        
        def browse_source(self):
            folder = filedialog.askdirectory(title="Select FHIR IG Source Directory")
            if folder:
                self.source_dir.set(folder)
                
        def save_configuration(self):
            """Save current configuration to YAML file"""
            config = {
                'source_repo': self.source_repo.get(),
                'source_branch': self.source_branch.get(),
                'source_dir': self.source_dir.get(),
                'history_repo': self.history_repo.get(),
                'history_branch': self.history_branch.get(),
                'webroot_repo': self.webroot_repo.get(),
                'webroot_branch': self.webroot_branch.get(),
                'enable_sparse_checkout': self.enable_sparse_checkout.get(),
                'sparse_dirs': self.sparse_dirs.get().split() if self.sparse_dirs.get().strip() else []
            }
            
            try:
                save_config(config)
                messagebox.showinfo("Success", "✅ Configuration saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"❌ Failed to save configuration: {e}")
                
        def show_progress(self, text="Processing..."):
            """Show beautiful progress indicator"""
            self.progress_frame.pack(fill=tk.X, pady=20)
            self.progress_label.configure(text=text)
            self.progress_label.pack(pady=(0, 10))
            self.progress.pack(fill=tk.X)
            self.progress.start(10)
            
        def hide_progress(self):
            """Hide progress indicator"""
            self.progress.stop()
            self.progress_frame.pack_forget()
            
        def run_publisher_threaded(self):
            """Run the publisher in a separate thread to prevent GUI freezing"""
            def run_in_thread():
                try:
                    self.root.after(0, lambda: self.show_progress("🔄 Running FHIR IG Publisher..."))
                    
                    # Get sparse directories if enabled
                    sparse_dirs = None
                    if self.enable_sparse_checkout.get() and self.sparse_dirs.get().strip():
                        sparse_dirs = self.sparse_dirs.get().split()
                    
                    pub = ReleasePublisher(
                        source_dir=self.source_dir.get() or None,
                        source_repo=self.source_repo.get() or None,
                        source_branch=self.source_branch.get() or None,
                        webroot_repo=self.webroot_repo.get() or None,
                        webroot_branch=self.webroot_branch.get() or None,
                        history_repo=self.history_repo.get() or None,
                        history_branch=self.history_branch.get() or None,
                        sparse_dirs=sparse_dirs,
                        enable_sparse_checkout=self.enable_sparse_checkout.get()
                    )
                    pub.run()
                    
                    self.root.after(0, self.hide_progress)
                    self.root.after(0, lambda: messagebox.showinfo("Success", "🎉 Publication completed successfully!\n\nYour FHIR IG has been published."))
                    
                except Exception as e:
                    self.root.after(0, self.hide_progress)
                    self.root.after(0, lambda: messagebox.showerror("Error", f"❌ An error occurred:\n\n{str(e)}"))
                    
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            
        def run(self):
            self.root.mainloop()

# Web-based GUI with gorgeous styling
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
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
                
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                :root {
                    --primary: #6C63FF;
                    --primary-dark: #5A52D5;
                    --primary-light: #8B82FF;
                    --secondary: #FF6B9D;
                    --success: #00D4AA;
                    --warning: #FFB800;
                    --background: #F8F9FF;
                    --card: #FFFFFF;
                    --text: #2D3748;
                    --text-light: #718096;
                    --text-muted: #A0AEC0;
                    --border: #E2E8F0;
                    --shadow: rgba(99, 179, 237, 0.12);
                    --shadow-lg: rgba(99, 179, 237, 0.25);
                }
                
                body {
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 2rem;
                    line-height: 1.6;
                }
                
                .container {
                    max-width: 1000px;
                    margin: 0 auto;
                    background: var(--card);
                    border-radius: 24px;
                    box-shadow: 0 25px 50px -12px var(--shadow-lg);
                    overflow: hidden;
                    backdrop-filter: blur(20px);
                }
                
                .header {
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
                    color: white;
                    padding: 3rem;
                    text-align: center;
                    position: relative;
                    overflow: hidden;
                }
                
                .header::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="50" cy="50" r="1" fill="white" opacity="0.1"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    pointer-events: none;
                }
                
                .header-content {
                    position: relative;
                    z-index: 1;
                }
                
                .header-icon {
                    font-size: 4rem;
                    margin-bottom: 1rem;
                    display: inline-block;
                    animation: float 3s ease-in-out infinite;
                }
                
                @keyframes float {
                    0%, 100% { transform: translateY(0px); }
                    50% { transform: translateY(-10px); }
                }
                
                .header h1 {
                    font-size: 3rem;
                    font-weight: 700;
                    margin-bottom: 0.5rem;
                    letter-spacing: -0.025em;
                }
                
                .header p {
                    font-size: 1.25rem;
                    opacity: 0.9;
                    font-weight: 400;
                }
                
                .content {
                    padding: 3rem;
                }
                
                .tabs {
                    display: flex;
                    background: var(--background);
                    border-radius: 16px;
                    padding: 0.5rem;
                    margin-bottom: 2rem;
                    box-shadow: inset 0 2px 4px var(--shadow);
                }
                
                .tab {
                    flex: 1;
                    padding: 1rem 1.5rem;
                    background: none;
                    border: none;
                    border-radius: 12px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    color: var(--text-light);
                    position: relative;
                }
                
                .tab.active {
                    background: var(--card);
                    color: var(--primary);
                    box-shadow: 0 4px 12px var(--shadow);
                    transform: translateY(-1px);
                }
                
                .tab-content {
                    display: none;
                }
                
                .tab-content.active {
                    display: block;
                    animation: fadeInUp 0.5s ease-out;
                }
                
                @keyframes fadeInUp {
                    from {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .section {
                    background: var(--card);
                    border-radius: 20px;
                    padding: 2rem;
                    margin-bottom: 2rem;
                    box-shadow: 0 8px 32px var(--shadow);
                    border: 1px solid var(--border);
                    transition: all 0.3s ease;
                }
                
                .section:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 12px 40px var(--shadow-lg);
                }
                
                .section-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 2rem;
                    padding-bottom: 1rem;
                    border-bottom: 2px solid var(--background);
                }
                
                .section-icon {
                    font-size: 1.5rem;
                    margin-right: 0.75rem;
                }
                
                .section h3 {
                    color: var(--text);
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin: 0;
                }
                
                .field-group {
                    margin-bottom: 2rem;
                    position: relative;
                }
                
                .field-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 0.5rem;
                }
                
                .field-icon {
                    margin-right: 0.5rem;
                    color: var(--primary);
                }
                
                label {
                    font-weight: 600;
                    color: var(--text);
                    font-size: 1rem;
                }
                
                .field-description {
                    font-size: 0.875rem;
                    color: var(--text-muted);
                    margin-bottom: 1rem;
                    line-height: 1.5;
                }
                
                input[type="text"], input[type="url"] {
                    width: 100%;
                    padding: 1rem 1.25rem;
                    border: 2px solid var(--border);
                    border-radius: 12px;
                    font-size: 1rem;
                    font-family: inherit;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    background: var(--card);
                }
                
                input[type="text"]:focus, input[type="url"]:focus {
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.1);
                    transform: translateY(-1px);
                }
                
                .checkbox-container {
                    background: var(--background);
                    border-radius: 16px;
                    padding: 1.5rem;
                    border: 2px solid var(--border);
                    transition: all 0.3s ease;
                }
                
                .checkbox-container:hover {
                    border-color: var(--primary);
                }
                
                .checkbox-group {
                    display: flex;
                    align-items: center;
                    margin-bottom: 1rem;
                }
                
                input[type="checkbox"] {
                    width: 1.25rem;
                    height: 1.25rem;
                    margin-right: 0.75rem;
                    accent-color: var(--primary);
                    cursor: pointer;
                }
                
                .checkbox-label {
                    font-weight: 600;
                    color: var(--text);
                    cursor: pointer;
                }
                
                .sparse-input {
                    margin-top: 1rem;
                    transition: all 0.3s ease;
                }
                
                .sparse-input.disabled {
                    opacity: 0.5;
                    pointer-events: none;
                }
                
                .example-hint {
                    display: flex;
                    align-items: center;
                    margin-top: 0.75rem;
                    padding: 0.75rem;
                    background: rgba(108, 99, 255, 0.05);
                    border-radius: 8px;
                    border-left: 3px solid var(--primary);
                }
                
                .example-icon {
                    margin-right: 0.5rem;
                }
                
                .button-group {
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    margin-top: 3rem;
                    flex-wrap: wrap;
                }
                
                button {
                    padding: 1rem 2rem;
                    border: none;
                    border-radius: 12px;
                    font-size: 1rem;
                    font-weight: 600;
                    font-family: inherit;
                    cursor: pointer;
                    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                    position: relative;
                    overflow: hidden;
                }
                
                button::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: -100%;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                    transition: left 0.5s;
                }
                
                button:hover::before {
                    left: 100%;
                }
                
                .btn-primary {
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
                    color: white;
                    box-shadow: 0 4px 16px rgba(108, 99, 255, 0.3);
                }
                
                .btn-primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 24px rgba(108, 99, 255, 0.4);
                }
                
                .btn-secondary {
                    background: var(--card);
                    color: var(--text);
                    border: 2px solid var(--border);
                    box-shadow: 0 2px 8px var(--shadow);
                }
                
                .btn-secondary:hover {
                    border-color: var(--primary);
                    transform: translateY(-2px);
                    box-shadow: 0 4px 16px var(--shadow);
                }
                
                .progress {
                    display: none;
                    margin: 2rem 0;
                    text-align: center;
                    padding: 2rem;
                    background: var(--background);
                    border-radius: 16px;
                }
                
                .progress-text {
                    font-weight: 600;
                    color: var(--primary);
                    margin-bottom: 1rem;
                    font-size: 1.1rem;
                }
                
                .progress-bar {
                    width: 100%;
                    height: 8px;
                    background: var(--border);
                    border-radius: 4px;
                    overflow: hidden;
                    position: relative;
                }
                
                .progress-bar::after {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    height: 100%;
                    width: 100%;
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
                    animation: shimmer 2s ease-in-out infinite;
                }
                
                @keyframes shimmer {
                    0% { transform: translateX(-100%); }
                    100% { transform: translateX(100%); }
                }
                
                .success-message {
                    background: linear-gradient(135deg, var(--success) 0%, #00E5CC 100%);
                    color: white;
                    padding: 1.5rem;
                    border-radius: 12px;
                    text-align: center;
                    font-weight: 600;
                    margin-top: 1rem;
                    box-shadow: 0 4px 16px rgba(0, 212, 170, 0.3);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="header-content">
                        <div class="header-icon">🧬</div>
                        <h1>FHIR IG Publisher</h1>
                        <p>Beautiful interface for configuring and publishing FHIR Implementation Guides</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="tabs">
                        <button class="tab active" onclick="showTab('source')">📂 Source</button>
                        <button class="tab" onclick="showTab('repository')">🔗 Repository</button>
                        <button class="tab" onclick="showTab('advanced')">⚡ Advanced</button>
                    </div>
                    
                    <form id="publisherForm">
                        <div id="source" class="tab-content active">
                            <div class="section">
                                <div class="section-header">
                                    <span class="section-icon">📂</span>
                                    <h3>Source Configuration</h3>
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">🌐</span>
                                        <label for="sourceRepo">Source Repository URL</label>
                                    </div>
                                    <div class="field-description">Git repository containing your FHIR IG source files</div>
                                    <input type="url" id="sourceRepo" name="sourceRepo" value="https://github.com/WorldHealthOrganization/smart-dak-pnc">
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">🔀</span>
                                        <label for="sourceBranch">Source Branch</label>
                                    </div>
                                    <div class="field-description">Specific branch or tag to use from the source repository</div>
                                    <input type="text" id="sourceBranch" name="sourceBranch" value="v0.9.9_releaseCandidate">
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">📁</span>
                                        <label for="sourceDir">Local Source Directory</label>
                                    </div>
                                    <div class="field-description">Optional: Use existing local directory instead of cloning from repository</div>
                                    <input type="text" id="sourceDir" name="sourceDir">
                                </div>
                            </div>
                        </div>
                        
                        <div id="repository" class="tab-content">
                            <div class="section">
                                <div class="section-header">
                                    <span class="section-icon">🔗</span>
                                    <h3>Repository Configuration</h3>
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">📚</span>
                                        <label for="historyRepo">History Repository URL</label>
                                    </div>
                                    <div class="field-description">Repository containing the IG history template for version management</div>
                                    <input type="url" id="historyRepo" name="historyRepo" value="https://github.com/HL7/fhir-ig-history-template">
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">🌿</span>
                                        <label for="historyBranch">History Branch</label>
                                    </div>
                                    <div class="field-description">Branch to use from the history repository</div>
                                    <input type="text" id="historyBranch" name="historyBranch" value="main">
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">🌍</span>
                                        <label for="webrootRepo">Webroot Repository URL</label>
                                    </div>
                                    <div class="field-description">Repository containing web publishing templates and assets</div>
                                    <input type="url" id="webrootRepo" name="webrootRepo" value="https://github.com/WorldHealthOrganization/smart-html">
                                </div>
                                
                                <div class="field-group">
                                    <div class="field-header">
                                        <span class="field-icon">🌳</span>
                                        <label for="webrootBranch">Webroot Branch</label>
                                    </div>
                                    <div class="field-description">Branch to use from the webroot repository</div>
                                    <input type="text" id="webrootBranch" name="webrootBranch" value="main">
                                </div>
                            </div>
                        </div>
                        
                        <div id="advanced" class="tab-content">
                            <div class="section">
                                <div class="section-header">
                                    <span class="section-icon">⚡</span>
                                    <h3>Sparse Checkout Optimization</h3>
                                </div>
                                
                                <div class="checkbox-container">
                                    <div class="checkbox-group">
                                        <input type="checkbox" id="enableSparseCheckout" name="enableSparseCheckout">
                                        <label for="enableSparseCheckout" class="checkbox-label">Enable sparse checkout for webroot repository</label>
                                    </div>
                                    <div class="field-description">Optimize clone performance by downloading only specific folders instead of the entire repository</div>
                                    
                                    <div class="sparse-input disabled" id="sparseInput">
                                        <div class="field-group">
                                            <div class="field-header">
                                                <span class="field-icon">📁</span>
                                                <label for="sparseDirs">Folders to Download</label>
                                            </div>
                                            <div class="field-description">Space-separated list of directories to include in the clone</div>
                                            <input type="text" id="sparseDirs" name="sparseDirs" value="templates assets">
                                            
                                            <div class="example-hint">
                                                <span class="example-icon">💡</span>
                                                <span><strong>Example:</strong> templates assets css js images</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="button-group">
                            <button type="button" class="btn-secondary" onclick="saveConfig()">
                                💾 Save Configuration
                            </button>
                            <button type="submit" class="btn-primary">
                                🚀 Run Publisher
                            </button>
                        </div>
                        
                        <div class="progress" id="progress">
                            <div class="progress-text">🔄 Running FHIR IG Publisher...</div>
                            <div class="progress-bar"></div>
                        </div>
                    </form>
                </div>
            </div>
            
            <script>
                function showTab(tabName) {
                    // Hide all tab contents
                    document.querySelectorAll('.tab-content').forEach(content => {
                        content.classList.remove('active');
                    });
                    
                    // Remove active class from all tabs
                    document.querySelectorAll('.tab').forEach(tab => {
                        tab.classList.remove('active');
                    });
                    
                    // Show selected tab content
                    document.getElementById(tabName).classList.add('active');
                    
                    // Add active class to clicked tab
                    event.target.classList.add('active');
                }
                
                // Toggle sparse directories field
                document.getElementById('enableSparseCheckout').addEventListener('change', function() {
                    const sparseInput = document.getElementById('sparseInput');
                    if (this.checked) {
                        sparseInput.classList.remove('disabled');
                    } else {
                        sparseInput.classList.add('disabled');
                    }
                });
                
                // Form submission
                document.getElementById('publisherForm').addEventListener('submit', function(e) {
                    e.preventDefault();
                    
                    const progress = document.getElementById('progress');
                    progress.style.display = 'block';
                    progress.scrollIntoView({ behavior: 'smooth' });
                    
                    const formData = new FormData(this);
                    const config = {};
                    
                    for (let [key, value] of formData.entries()) {
                        config[key] = value;
                    }
                    
                    // Handle sparse directories
                    config.enableSparseCheckout = document.getElementById('enableSparseCheckout').checked;
                    if (config.enableSparseCheckout) {
                        config.sparseDirs = config.sparseDirs ? config.sparseDirs.split(' ') : ['templates', 'assets'];
                    }
                    
                    console.log('Configuration:', config);
                    
                    // Simulate processing time
                    setTimeout(() => {
                        progress.style.display = 'none';
                        
                        const successDiv = document.createElement('div');
                        successDiv.className = 'success-message';
                        successDiv.innerHTML = '🎉 Publication completed successfully!<br>Your FHIR IG has been published.';
                        
                        const buttonGroup = document.querySelector('.button-group');
                        buttonGroup.insertAdjacentElement('afterend', successDiv);
                        
                        successDiv.scrollIntoView({ behavior: 'smooth' });
                    }, 4000);
                });
                
                function saveConfig() {
                    const successDiv = document.createElement('div');
                    successDiv.className = 'success-message';
                    successDiv.innerHTML = '💾 Configuration saved successfully!';
                    successDiv.style.marginTop = '1rem';
                    
                    const buttonGroup = document.querySelector('.button-group');
                    
                    // Remove any existing success messages
                    const existingSuccess = buttonGroup.parentNode.querySelector('.success-message');
                    if (existingSuccess) {
                        existingSuccess.remove();
                    }
                    
                    buttonGroup.insertAdjacentElement('afterend', successDiv);
                    
                    // Remove success message after 3 seconds
                    setTimeout(() => {
                        if (successDiv.parentNode) {
                            successDiv.remove();
                        }
                    }, 3000);
                }
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
        print(f"🌐 Beautiful web interface opened: file://{html_file}")

def main():
    parser = argparse.ArgumentParser(description="FHIR IG Publisher Release Utility")
    parser.add_argument('--gui', action='store_true', help='Launch beautiful GUI interface')
    parser.add_argument('--web-gui', action='store_true', help='Launch gorgeous web-based GUI')
    parser.add_argument('--source', type=str, help='Path to the IG source folder')
    parser.add_argument('--source-repo', type=str, help='URL to the IG source repository')
    parser.add_argument('--source-branch', type=str, help='Branch name for IG source')
    parser.add_argument('--webroot-repo', type=str, help='Webroot repo URL')
    parser.add_argument('--webroot-branch', type=str, help='Webroot branch name')
    parser.add_argument('--history-repo', type=str, help='History repo URL')
    parser.add_argument('--history-branch', type=str, help='History branch name')
    parser.add_argument('--sparse', nargs='*', help='Sparse checkout folders for webroot')
    parser.add_argument('--enable-sparse', action='store_true', help='Enable sparse checkout')
    args = parser.parse_args()

    if args.web_gui:
        web_gui = WebIGPublisherGUI()
        web_gui.run()
    elif args.gui:
        if not tk:
            print("❌ GUI not available: tkinter not found")
            sys.exit(1)
        gui = BeautifulIGPublisherGUI()
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
            sparse_dirs=args.sparse,
            enable_sparse_checkout=args.enable_sparse
        )
        publisher.run()

if __name__ == '__main__':
    main()