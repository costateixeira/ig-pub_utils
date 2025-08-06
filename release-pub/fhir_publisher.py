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
                'primary': '#6C63FF',
                'primary_dark': '#5A52D5',
                'primary_light': '#8B82FF',
                'secondary': '#FF6B9D',
                'success': '#00D4AA',
                'warning': '#FFB800',
                'background': '#F8F9FF',
                'card': '#FFFFFF',
                'text': '#2D3748',
                'text_light': '#718096',
                'text_muted': '#A0AEC0',
                'border': '#E2E8F0'
            }
            
            # Configure root window
            self.root.configure(bg=self.colors['background'])
            
            # Main styling configurations...
            self.style.configure('Card.TFrame', 
                               background=self.colors['card'],
                               relief='flat',
                               borderwidth=0)
            
            self.style.configure('Modern.TEntry',
                               fieldbackground='white',
                               bordercolor=self.colors['border'],
                               borderwidth=2,
                               padding=(12, 12))  # Increased padding
            
            self.style.configure('Primary.TButton',
                               font=('Segoe UI', 11, 'bold'),
                               foreground='white',
                               borderwidth=0,
                               padding=(25, 12))
            
            self.style.map('Primary.TButton',
                          background=[('active', self.colors['primary_dark']),
                                    ('!active', self.colors['primary'])])
            
        def setup_variables(self, config):
            self.source_repo = tk.StringVar(value=config.get('source_repo', 'https://github.com/WorldHealthOrganization/smart-dak-pnc'))
            self.source_branch = tk.StringVar(value=config.get('source_branch', 'v0.9.9_releaseCandidate'))
            self.source_dir = tk.StringVar(value=config.get('source_dir', ''))
            self.history_repo = tk.StringVar(value=config.get('history_repo', 'https://github.com/HL7/fhir-ig-history-template'))
            self.history_branch = tk.StringVar(value=config.get('history_branch', 'main'))
            self.webroot_repo = tk.StringVar(value=config.get('webroot_repo', 'https://github.com/WorldHealthOrganization/smart-html'))
            self.webroot_branch = tk.StringVar(value=config.get('webroot_branch', 'main'))
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
            # Simplified widget creation for tkinter version
            main_frame = ttk.Frame(self.root, style='Card.TFrame', padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Title
            ttk.Label(main_frame, text="🧬 FHIR IG Publisher", 
                     font=('Segoe UI', 18, 'bold')).pack(pady=20)
            
            # Create basic form fields
            self.create_basic_form(main_frame)
            
            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="💾 Save", 
                      command=self.save_configuration).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="🚀 Run Publisher", 
                      command=self.run_publisher_threaded,
                      style='Primary.TButton').pack(side=tk.RIGHT, padx=10)
        
        def create_basic_form(self, parent):
            # Basic form implementation for tkinter
            fields = [
                ("Source Repository:", self.source_repo),
                ("Source Branch:", self.source_branch),
                ("Local Source Dir:", self.source_dir),
                ("History Repo:", self.history_repo),
                ("History Branch:", self.history_branch),
                ("Webroot Repo:", self.webroot_repo),
                ("Webroot Branch:", self.webroot_branch),
            ]
            
            for label, var in fields:
                frame = ttk.Frame(parent)
                frame.pack(fill=tk.X, pady=5)
                ttk.Label(frame, text=label, width=20).pack(side=tk.LEFT)
                ttk.Entry(frame, textvariable=var, style='Modern.TEntry').pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Sparse checkout
            sparse_frame = ttk.Frame(parent)
            sparse_frame.pack(fill=tk.X, pady=10)
            
            ttk.Checkbutton(sparse_frame, text="Enable sparse checkout", 
                           variable=self.enable_sparse_checkout).pack(anchor='w')
            ttk.Entry(sparse_frame, textvariable=self.sparse_dirs, 
                     style='Modern.TEntry').pack(fill=tk.X, pady=5)
        
        def save_configuration(self):
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
                messagebox.showinfo("Success", "✅ Configuration saved!")
            except Exception as e:
                messagebox.showerror("Error", f"❌ Failed to save: {e}")
                
        def run_publisher_threaded(self):
            def run_in_thread():
                try:
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
                    
                    self.root.after(0, lambda: messagebox.showinfo("Success", "🎉 Publication completed!"))
                    
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"❌ Error: {str(e)}"))
                    
            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            
        def run(self):
            self.root.mainloop()

# Web-based GUI
class WebIGPublisherGUI:
    def __init__(self, port=8080):
        self.port = port
        self.config = load_config()
        
    def get_html_template(self):
        """Load HTML template from separate file"""
        template_file = os.path.join(os.path.dirname(__file__), 'fhir_publisher_ui.html')
        
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # Fallback to embedded template if file doesn't exist
            return self.create_embedded_template()
    
    def create_embedded_template(self):
        """Fallback embedded template"""
        return """
        <!DOCTYPE html>
        <html><head><title>FHIR IG Publisher</title></head>
        <body>
        <h1>FHIR IG Publisher</h1>
        <p>Please create fhir_publisher_ui.html for the full interface.</p>
        <form>
            <input type="text" placeholder="Source Repository" name="sourceRepo">
            <button type="submit">Run Publisher</button>
        </form>
        </body></html>
        """
    
    def run(self):
        """Start the web server and open the browser"""
        html_content = self.get_html_template()
        
        # Write HTML to temporary file with UTF-8 encoding
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html_content)
            html_file = f.name
        
        # Open in browser
        webbrowser.open(f'file://{html_file}')
        print(f"🌐 Web interface opened: file://{html_file}")

def main():
    parser = argparse.ArgumentParser(description="FHIR IG Publisher Release Utility")
    parser.add_argument('--gui', action='store_true', help='Launch GUI interface')
    parser.add_argument('--web-gui', action='store_true', help='Launch web-based GUI')
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