import json
import os
from collections import defaultdict
import subprocess
from data.configurations import bugsinpy_base, bugsinpy_info_file, proj_base_dir, focal_proj_base
from glob import glob
import charset_normalizer

def detect_and_read_file(file_path):
    # Detect encoding
    with open(file_path, 'rb') as f:
        raw_data = f.read()
    detected = charset_normalizer.detect(raw_data)
    encoding = detected['encoding']
    
    if not encoding:
        raise ValueError("Unable to detect encoding for the file.")
    
    # Read the file using the detected encoding
    with open(file_path, 'r', encoding=encoding) as f:
        content = f.read()
    return content

def setup_envs(info_file):
    # Load project data from JSON file
    with open(info_file, 'r') as f:
        all_bug_data = json.load(f)
    
    all_requirements = set()
    for proj_name, bugs in all_bug_data.items():
        for bug_id, bug_info in bugs.items():

            requirements_files = glob(f'/data/yangchen/llm_teut/data/benchmarks/bugsinpy/{proj_name}/*/requirements.txt')
            
            for requirements_file in requirements_files:
                # detect the encoding then open and read
                reqs = detect_and_read_file(requirements_file).split('\n')
                all_requirements.update(reqs)
    
    for req in all_requirements:
        try:
            subprocess.run(['/data/yangchen/anaconda3/envs/teut/bin/pip', 'install', req], check=True)
            print(f"Installed {req} successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {req}: {e}")
            continue
        except Exception as e:
            print(f"Failed to install {req}: {e}")
            continue

setup_envs(bugsinpy_info_file)