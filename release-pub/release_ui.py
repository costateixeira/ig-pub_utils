import os
import sys
import subprocess
import logging
import argparse
import shutil
import json
import yaml

try:
    import git
except ImportError:
    print("Installing GitPython...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'gitpython'])
    import git

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
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

if tk:
    class IGPublisherGUI:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("FHIR IG Publisher")
            config = load_config()

            self.source_repo = tk.StringVar(value=config.get('source_repo', ''))
            self.source_branch = tk.StringVar(value=config.get('source_branch', ''))
            self.source_dir = tk.StringVar(value=config.get('source_dir', ''))
            self.history_repo = tk.StringVar(value=config.get('history_repo', ''))
            self.history_branch = tk.StringVar(value=config.get('history_branch', ''))
            self.webroot_repo = tk.StringVar(value=config.get('webroot_repo', ''))
            self.webroot_branch = tk.StringVar(value=config.get('webroot_branch', ''))
            self.sparse_dirs = tk.StringVar(value=' '.join(config.get('sparse_dirs', [])))

            row = 0
            def add_entry(label, var):
                nonlocal row
                ttk.Label(self.root, text=label).grid(row=row, column=0, sticky="e")
                ttk.Entry(self.root, textvariable=var, width=50).grid(row=row, column=1, columnspan=2)
                row += 1

            add_entry("IG Source Repo URL:", self.source_repo)
            add_entry("IG Source Branch:", self.source_branch)
            add_entry("(Optional) Local Source Folder:", self.source_dir)
            ttk.Button(self.root, text="Browse", command=self.browse_source).grid(row=row-1, column=3)

            add_entry("History Repo URL:", self.history_repo)
            add_entry("History Branch:", self.history_branch)
            add_entry("Webroot Repo URL:", self.webroot_repo)
            add_entry("Webroot Branch:", self.webroot_branch)
            add_entry("Sparse Folders (space-separated):", self.sparse_dirs)

            ttk.Button(self.root, text="Run", command=self.run_publisher).grid(row=row, column=1, pady=10)

        def browse_source(self):
            folder = filedialog.askdirectory()
            if folder:
                self.source_dir.set(folder)

        def run_publisher(self):
            try:
                pub = ReleasePublisher(
                    source_dir=self.source_dir.get() or None,
                    source_repo=self.source_repo.get() or None,
                    source_branch=self.source_branch.get() or None,
                    webroot_repo=self.webroot_repo.get() or None,
                    webroot_branch=self.webroot_branch.get() or None,
                    history_repo=self.history_repo.get() or None,
                    history_branch=self.history_branch.get() or None,
                    sparse_dirs=self.sparse_dirs.get().split() if self.sparse_dirs.get().strip() else None
                )
                pub.run()
                messagebox.showinfo("Done", "Publication completed successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred: {e}")

        def run(self):
            self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="FHIR IG Publisher Release Utility")
    parser.add_argument('--gui', action='store_true', help='Launch GUI interface')
    parser.add_argument('--source', type=str, help='Path to the IG source folder')
    parser.add_argument('--source-repo', type=str, help='URL to the IG source repository')
    parser.add_argument('--source-branch', type=str, help='Branch name for IG source')
    parser.add_argument('--webroot-repo', type=str, help='Webroot repo URL')
    parser.add_argument('--webroot-branch', type=str, help='Webroot branch name')
    parser.add_argument('--history-repo', type=str, help='History repo URL')
    parser.add_argument('--history-branch', type=str, help='History branch name')
    parser.add_argument('--sparse', nargs='*', help='Sparse checkout folders for webroot')
    args = parser.parse_args()

    if args.gui:
        if not tk:
            print("❌ GUI not available: tkinter not found")
            sys.exit(1)
        gui = IGPublisherGUI()
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
