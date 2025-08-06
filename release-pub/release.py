#!/usr/bin/env python3
"""
IG Publisher Build Script
Handles sparse checkout, building, and deployment of FHIR Implementation Guides
"""

import os
import sys
import json
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BuildConfig:
    """Configuration for the IG build process"""
    ig_folder: str = 'hiv'
    source_repo: str = ''  # Current repo (from GitHub context)
    webroot_repo: str = 'WorldHealthOrganization/smart-html'
    history_template_repo: str = 'HL7/fhir-ig-history-template'
    ig_registry_repo: str = 'FHIR/ig-registry'
    work_dir: Path = Path.cwd()
    github_token: Optional[str] = None
    push_changes: bool = False
    create_pr: bool = True
    deploy_to_pages: bool = True
    max_file_size_mb: int = 100


class IGPublisher:
    """Main class for handling IG publishing workflow"""
    
    def __init__(self, config: BuildConfig):
        self.config = config
        self.paths = self._setup_paths()
        
    def _setup_paths(self) -> Dict[str, Path]:
        """Setup working directory paths"""
        return {
            'source': self.config.work_dir / 'source',
            'webroot': self.config.work_dir / 'webroot',
            'history_template': self.config.work_dir / 'history-template',
            'ig_registry': self.config.work_dir / 'ig-registry',
            'cache': self.config.work_dir / 'fhir-package-cache',
            'deploy': self.config.work_dir / 'deploy',
            'release_assets': self.config.work_dir / 'release-assets',
            'temp': self.config.work_dir / 'temp',
            'publisher_jar': self.config.work_dir / 'publisher.jar'
        }
    
    def run_command(self, cmd: str, cwd: Optional[Path] = None, 
                   check: bool = True, shell: bool = True) -> subprocess.CompletedProcess:
        """Execute shell command with error handling"""
        logger.debug(f"Running: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=shell,
                cwd=cwd or self.config.work_dir,
                capture_output=True,
                text=True,
                check=check
            )
            if result.stdout:
                logger.debug(f"Output: {result.stdout}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {cmd}")
            logger.error(f"Error: {e.stderr}")
            raise
    
    def checkout_repo(self, repo: str, path: Path, depth: int = 1):
        """Checkout a repository with shallow clone"""
        logger.info(f"Checking out {repo} to {path}")
        if path.exists():
            shutil.rmtree(path)
        
        cmd = f"git clone --depth={depth} https://github.com/{repo}.git {path}"
        self.run_command(cmd)
    
    def sparse_checkout_webroot(self):
        """Perform sparse checkout of webroot repository"""
        logger.info(f"Sparse checkout of {self.config.webroot_repo} (folder: {self.config.ig_folder})")
        
        webroot = self.paths['webroot']
        if webroot.exists():
            shutil.rmtree(webroot)
        
        # Clone with sparse checkout and partial clone for minimal size
        commands = [
            f"git clone --depth=1 --filter=blob:none --sparse "
            f"https://github.com/{self.config.webroot_repo}.git {webroot}",
            
            f"cd {webroot} && git sparse-checkout init",
            f"cd {webroot} && git sparse-checkout set {self.config.ig_folder}",
            
            # Configure git for potential commits
            f"cd {webroot} && git config user.email 'github-actions[bot]@users.noreply.github.com'",
            f"cd {webroot} && git config user.name 'GitHub Actions Bot'"
        ]
        
        for cmd in commands:
            self.run_command(cmd)
        
        # Verify sparse checkout worked
        logger.info(f"Webroot contents: {list(webroot.iterdir())}")
    
    def setup_publisher(self):
        """Download and setup IG publisher"""
        logger.info("Setting up IG publisher")
        
        # Create cache directory
        self.paths['cache'].mkdir(exist_ok=True)
        
        # Download publisher.jar if not exists
        if not self.paths['publisher_jar'].exists():
            logger.info("Downloading publisher.jar")
            cmd = (
                "curl -L https://github.com/HL7/fhir-ig-publisher/releases/"
                f"latest/download/publisher.jar -o {self.paths['publisher_jar']}"
            )
            self.run_command(cmd)
        
        # Install sushi if needed (in Docker or locally)
        if self._is_docker_available():
            cmd = (
                f"docker run --rm -v {self.config.work_dir}:/workspace "
                "-w /workspace hl7fhir/ig-publisher-base:latest "
                "/bin/sh -c 'npm install -g fsh-sushi'"
            )
            self.run_command(cmd, check=False)
    
    def _is_docker_available(self) -> bool:
        """Check if Docker is available"""
        result = self.run_command("docker --version", check=False)
        return result.returncode == 0
    
    def build_ig(self):
        """Run the IG publisher"""
        logger.info("Building IG")
        
        java_cmd = (
            f"java -Xmx4g -jar {self.paths['publisher_jar']} publisher "
            f"-ig {self.paths['source']} "
            f"-package-cache-folder {self.paths['cache']}"
        )
        
        if self._is_docker_available():
            cmd = (
                f"docker run --rm -v {self.config.work_dir}:/workspace "
                f"-w /workspace hl7fhir/ig-publisher-base:latest {java_cmd}"
            )
        else:
            cmd = java_cmd
        
        self.run_command(cmd)
    
    def publish_release(self):
        """Run publisher for release"""
        logger.info("Publishing release")
        
        java_cmd = (
            f"java -Xmx4g -Dfile.encoding=UTF-8 -jar {self.paths['publisher_jar']} "
            f"-go-publish "
            f"-package-cache-folder {self.paths['cache']} "
            f"-source {self.paths['source']} "
            f"-web {self.paths['webroot']} "
            f"-temp {self.paths['temp']} "
            f"-registry {self.paths['ig_registry']}/fhir-ig-list.json "
            f"-history {self.paths['history_template']} "
            f"-templates {self.paths['webroot']}/templates"
        )
        
        if self._is_docker_available():
            cmd = (
                f"docker run --rm -v {self.config.work_dir}:/workspace "
                f"-w /workspace hl7fhir/ig-publisher-base:latest /bin/sh -c \"{java_cmd}\""
            )
        else:
            cmd = java_cmd
        
        self.run_command(cmd)
    
    def prepare_deployment(self):
        """Prepare files for deployment, handling large files"""
        logger.info("Preparing deployment")
        
        self.paths['deploy'].mkdir(exist_ok=True)
        self.paths['release_assets'].mkdir(exist_ok=True)
        
        # Find and move large files
        webroot = self.paths['webroot']
        max_size = self.config.max_file_size_mb * 1024 * 1024
        
        for file in webroot.rglob('*'):
            if file.is_file() and file.stat().st_size > max_size:
                logger.info(f"Moving large file: {file.name} ({file.stat().st_size / 1024 / 1024:.1f}MB)")
                shutil.move(str(file), str(self.paths['release_assets'] / file.name))
        
        # Copy remaining files to deploy
        shutil.copytree(webroot, self.paths['deploy'], dirs_exist_ok=True)
        
        # Move package.tgz if exists
        package_file = self.paths['source'] / 'output' / 'package.tgz'
        if package_file.exists():
            shutil.move(str(package_file), str(self.paths['release_assets'] / 'package.tgz'))
    
    def push_changes(self):
        """Push changes back to webroot repository"""
        if not self.config.push_changes:
            logger.info("Skipping push (push_changes=False)")
            return
        
        logger.info("Pushing changes to webroot repository")
        
        webroot = self.paths['webroot']
        branch_name = f"update-{self.config.ig_folder}-{datetime.now():%Y%m%d-%H%M%S}"
        
        commands = [
            f"cd {webroot} && git checkout -b {branch_name}",
            f"rsync -av --exclude='.git/' --delete {self.paths['deploy']}/{self.config.ig_folder}/ "
            f"{webroot}/{self.config.ig_folder}/",
            f"cd {webroot} && git add {self.config.ig_folder}/",
        ]
        
        for cmd in commands:
            self.run_command(cmd)
        
        # Check if there are changes
        result = self.run_command(f"cd {webroot} && git diff --staged --quiet", check=False)
        
        if result.returncode == 0:
            logger.info("No changes to commit")
            return
        
        # Commit and push
        commit_msg = f"Update {self.config.ig_folder} IG content"
        self.run_command(f"cd {webroot} && git commit -m '{commit_msg}'")
        
        if self.config.github_token:
            # Push with token
            remote_url = f"https://{self.config.github_token}@github.com/{self.config.webroot_repo}.git"
            self.run_command(f"cd {webroot} && git remote set-url origin {remote_url}")
        
        self.run_command(f"cd {webroot} && git push origin {branch_name}")
        
        if self.config.create_pr:
            logger.info(f"Branch {branch_name} pushed. Create PR manually or use GitHub CLI.")
    
    def run(self):
        """Execute the complete build workflow"""
        try:
            logger.info(f"Starting IG Publisher for folder: {self.config.ig_folder}")
            
            # Checkout repositories
            logger.info("Step 1: Checking out repositories")
            self.checkout_repo('.', self.paths['source'])  # Current repo
            self.checkout_repo(self.config.history_template_repo, self.paths['history_template'])
            self.checkout_repo(self.config.ig_registry_repo, self.paths['ig_registry'])
            self.sparse_checkout_webroot()
            
            # Setup publisher
            logger.info("Step 2: Setting up publisher")
            self.setup_publisher()
            
            # Build IG
            logger.info("Step 3: Building IG")
            self.build_ig()
            
            # Publish release
            logger.info("Step 4: Publishing release")
            self.publish_release()
            
            # Prepare deployment
            logger.info("Step 5: Preparing deployment")
            self.prepare_deployment()
            
            # Push changes (if configured)
            logger.info("Step 6: Pushing changes")
            self.push_changes()
            
            logger.info("✅ IG Publisher completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Build failed: {e}")
            raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='FHIR IG Publisher Build Script')
    parser.add_argument('--ig-folder', default='hiv', help='IG folder in webroot repo')
    parser.add_argument('--webroot-repo', default='WorldHealthOrganization/smart-html',
                       help='Webroot repository')
    parser.add_argument('--push', action='store_true', help='Push changes to webroot')
    parser.add_argument('--no-pr', action='store_false', dest='create_pr',
                       help='Push directly without creating PR')
    parser.add_argument('--work-dir', type=Path, default=Path.cwd(),
                       help='Working directory')
    parser.add_argument('--github-token', help='GitHub token for pushing changes')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create config
    config = BuildConfig(
        ig_folder=args.ig_folder,
        webroot_repo=args.webroot_repo,
        work_dir=args.work_dir,
        github_token=args.github_token or os.environ.get('GITHUB_TOKEN'),
        push_changes=args.push,
        create_pr=args.create_pr
    )
    
    # Run publisher
    publisher = IGPublisher(config)
    publisher.run()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
