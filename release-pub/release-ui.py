#!/usr/bin/env python3
"""
IG Publisher GUI
Simple GUI interface for the IG Publisher script
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

class IGPublisherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FHIR IG Publisher")
        self.root.geometry("800x600")
        
        # Variables
        self.ig_folder = tk.StringVar(value="hiv")
        self.webroot_repo = tk.StringVar(value="WorldHealthOrganization/smart-html")
        self.work_dir = tk.StringVar(value=os.getcwd())
        self.push_changes = tk.BooleanVar(value=False)
        self.create_pr = tk.BooleanVar(value=True)
        self.github_token = tk.StringVar()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the GUI interface"""
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        config_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # IG Folder
        ttk.Label(config_frame, text="IG Folder:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.ig_folder, width=40).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Webroot Repository
        ttk.Label(config_frame, text="Webroot Repo:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.webroot_repo, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Working Directory
        ttk.Label(config_frame, text="Work Directory:").grid(row=2, column=0, sticky=tk.W, pady=2)
        work_dir_frame = ttk.Frame(config_frame)
        work_dir_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Entry(work_dir_frame, textvariable=self.work_dir, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(work_dir_frame, text="Browse", command=self.browse_directory).pack(side=tk.RIGHT, padx=(5, 0))
        
        # GitHub Token
        ttk.Label(config_frame, text="GitHub Token:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(config_frame, textvariable=self.github_token, show="*", width=40).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding="10")
        options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(options_frame, text="Push changes to repository", 
                       variable=self.push_changes).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="Create Pull Request", 
                       variable=self.create_pr).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.build_button = ttk.Button(button_frame, text="Start Build", 
                                      command=self.start_build, style="Accent.TButton")
        self.build_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", 
                                     command=self.stop_build, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Clear Log", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Log output
        log_frame = ttk.LabelFrame(main_frame, text="Output Log", padding="10")
        log_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        config_frame.columnconfigure(1, weight=1)
        
        # Style configuration
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="blue")
        
        self.process = None
        
    def browse_directory(self):
        """Browse for working directory"""
        directory = filedialog.askdirectory(initialdir=self.work_dir.get())
        if directory:
            self.work_dir.set(directory)
    
    def log(self, message, level="INFO"):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}\n"
        
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Clear the log output"""
        self.log_text.delete(1.0, tk.END)
    
    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def start_build(self):
        """Start the build process"""
        # Validate inputs
        if not self.ig_folder.get():
            messagebox.showerror("Error", "Please specify an IG folder")
            return
        
        # Disable build button, enable stop
        self.build_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress.start(10)
        
        # Start build in separate thread
        thread = threading.Thread(target=self.run_build)
        thread.daemon = True
        thread.start()
    
    def run_build(self):
        """Run the build process"""
        try:
            self.update_status("Building...")
            self.log("Starting IG Publisher build", "INFO")
            
            # Prepare command
            cmd = [
                sys.executable,
                "ig_publisher.py",
                "--ig-folder", self.ig_folder.get(),
                "--webroot-repo", self.webroot_repo.get(),
                "--work-dir", self.work_dir.get()
            ]
            
            if self.push_changes.get():
                cmd.append("--push")
            
            if not self.create_pr.get():
                cmd.append("--no-pr")
            
            if self.github_token.get():
                cmd.extend(["--github-token", self.github_token.get()])
            
            # Run the process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    # Parse log level from output
                    if "[ERROR]" in line:
                        self.log(line.strip(), "ERROR")
                    elif "[WARN]" in line:
                        self.log(line.strip(), "WARN")
                    else:
                        self.log(line.strip(), "INFO")
            
            # Wait for process to complete
            self.process.wait()
            
            if self.process.returncode == 0:
                self.update_status("Build completed successfully!")
                self.log("✅ Build completed successfully!", "SUCCESS")
                messagebox.showinfo("Success", "Build completed successfully!")
            else:
                self.update_status("Build failed")
                self.log("❌ Build failed", "ERROR")
                messagebox.showerror("Error", "Build failed. Check the log for details.")
                
        except Exception as e:
            self.update_status("Build error")
            self.log(f"Error: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Build error: {str(e)}")
            
        finally:
            # Re-enable buttons
            self.build_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.progress.stop()
            self.process = None
    
    def stop_build(self):
        """Stop the build process"""
        if self.process:
            self.process.terminate()
            self.log("Build process terminated by user", "WARN")
            self.update_status("Build stopped")
            
            self.build_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.progress.stop()


def main():
    """Main entry point for GUI"""
    root = tk.Tk()
    app = IGPublisherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
