#!/usr/bin/env python3
"""
Simplified Flexo Parameter Optimizer
Performs grid search over Flexo compiler parameters to find optimal configurations.
"""

import subprocess
import re
import json
import time
from itertools import product
from datetime import datetime
from pathlib import Path

# Configuration - Edit these parameter ranges as needed
# PARAMETER_RANGES = {
#     'RET_WM_DIV_ROUNDS': [1, 3, 5, 10, 15],
#     'WM_DELAY': [128, 256, 512, 1024],
#     'WR_OFFSET': [576, 960, 1088, 1216]
# }
PARAMETER_RANGES = {
    'RET_WM_DIV_ROUNDS': range(1, 51),
    # 'WM_DELAY': [64, 96, 128, 160, 192, 256],
    'WR_OFFSET': [192, 320, 448, 576, 960, 1088]
}

ITERATIONS = 5000  # Number of test iterations per configuration
DOCKER_IMAGE = "flexo"
WORK_DIR = "/flexo"

class FlexoOptimizer:
    def __init__(self):
        self.output_dir = Path("grid_search_results")
        self.output_dir.mkdir(exist_ok=True)
        self.results = []
        self.best_config = None
        self.best_score = 0.0
        
    def run_command(self, cmd, timeout=300):
        """Execute docker command with timeout"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
    
    def build_and_test(self, config):
        """Build Flexo gates with configuration and run test"""
        print(f"Testing: {config}")
        
        # Clean previous build
        clean_cmd = f'docker run --rm -v "$(pwd)":{WORK_DIR} {DOCKER_IMAGE} make -C {WORK_DIR}/circuits/gates/ clean'
        success, _, stderr = self.run_command(clean_cmd)
        if not success:
            print(f"Clean failed: {stderr}")
            return None
            
        # Build gates
        build_cmd = f'docker run --rm -v "$(pwd)":{WORK_DIR} {DOCKER_IMAGE} make -C {WORK_DIR}/circuits/gates/'
        success, _, stderr = self.run_command(build_cmd)
        if not success:
            print(f"Build failed: {stderr}")
            return None
        
        # Create environment variables for compilation
        env_vars = " ".join([f"{k}={v}" for k, v in config.items()])
        
        # Compile with Flexo
        compile_cmd = f'''docker run --rm -v "$(pwd)":{WORK_DIR} {DOCKER_IMAGE} bash -c "cd {WORK_DIR} && {env_vars} ./compile.sh circuits/gates/test.ll circuits/gates/test-wm.ll"'''
        success, _, stderr = self.run_command(compile_cmd)
        if not success:
            print(f"Compilation failed: {stderr}")
            return None
        
        # Build executable
        exe_cmd = f'docker run --rm -v "$(pwd)":{WORK_DIR} {DOCKER_IMAGE} clang-17 {WORK_DIR}/circuits/gates/test-wm.ll -o {WORK_DIR}/circuits/gates/gates.elf -lm -lstdc++'
        success, _, stderr = self.run_command(exe_cmd)
        if not success:
            print(f"Executable build failed: {stderr}")
            return None
            
        # Run test
        test_cmd = f'docker run --rm -v "$(pwd)":{WORK_DIR} {DOCKER_IMAGE} bash -c "cd {WORK_DIR} && echo {ITERATIONS} | ./circuits/gates/gates.elf"'
        success, stdout, stderr = self.run_command(test_cmd, timeout=600)
        if not success:
            print(f"Test failed: {stderr}")
            return None
        
        return self.parse_results(stdout)
    
    def parse_results(self, output):
        """Parse gate test output"""
        results = {}
        lines = output.strip().split('\n')
        current_gate = None
        
        for line in lines:
            # Find gate headers like "=== AND gate ==="
            gate_match = re.match(r'=== (\w+) gate ===', line)
            if gate_match:
                current_gate = gate_match.group(1)
                continue
            
            # Find accuracy results
            accuracy_match = re.match(r'Accuracy: ([\d.]+)%, Error detected: ([\d.]+)%, Undetected error: ([\d.]+)%', line)
            if accuracy_match and current_gate:
                results[current_gate] = {
                    'accuracy': float(accuracy_match.group(1)),
                    'error_detected': float(accuracy_match.group(2)),
                    'undetected_error': float(accuracy_match.group(3))
                }
        
        return results
    
    def calculate_score(self, gate_results):
        """Calculate overall performance score"""
        if not gate_results:
            return 0.0
        
        total_score = 0.0
        for gate_name, metrics in gate_results.items():
            # Score based on accuracy, heavily penalize undetected errors
            gate_score = metrics['accuracy'] - (metrics['undetected_error'] * 3)
            total_score += max(0, gate_score)
        
        return total_score / len(gate_results)
    
    def optimize(self):
        """Run optimization across all parameter combinations"""
        print("Starting Flexo parameter optimization...")
        print(f"Parameter ranges: {PARAMETER_RANGES}")
        
        # Generate all parameter combinations
        param_names = list(PARAMETER_RANGES.keys())
        param_values = [PARAMETER_RANGES[name] for name in param_names]
        combinations = list(product(*param_values))
        
        print(f"Testing {len(combinations)} configurations...")
        
        for i, combination in enumerate(combinations):
            config = dict(zip(param_names, combination))
            
            print(f"\n--- Configuration {i+1}/{len(combinations)} ---")
            gate_results = self.build_and_test(config)
            
            if gate_results:
                score = self.calculate_score(gate_results)
                
                result = {
                    'config': config,
                    'gate_results': gate_results,
                    'score': score,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.results.append(result)
                
                print(f"Score: {score:.2f}")
                for gate_name, metrics in gate_results.items():
                    print(f"  {gate_name}: {metrics['accuracy']:.1f}% accuracy, {metrics['undetected_error']:.1f}% undetected")
                
                # Track best configuration
                if score > self.best_score:
                    self.best_score = score
                    self.best_config = result
                    print(f"*** NEW BEST! Score: {self.best_score:.2f} ***")
            
            time.sleep(1)  # Brief pause between tests
        
        self.save_and_summarize()
    
    def save_and_summarize(self):
        """Save results and print summary"""
        if not self.results:
            print("No results to save")
            return
        
        # Save results to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.output_dir / f"results_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n{'='*50}")
        print("OPTIMIZATION COMPLETE")
        print(f"{'='*50}")
        print(f"Configurations tested: {len(self.results)}")
        print(f"Results saved to: {results_file}")
        print(f"Best score: {self.best_score:.2f}")
        
        if self.best_config:
            print(f"\nBest configuration:")
            for key, value in self.best_config['config'].items():
                print(f"  {key} = {value}")
            
            print(f"\nBest results:")
            for gate_name, metrics in self.best_config['gate_results'].items():
                acc = metrics['accuracy']
                undet = metrics['undetected_error']
                print(f"  {gate_name}: {acc:.1f}% accuracy, {undet:.1f}% undetected error")

def main():
    optimizer = FlexoOptimizer()
    
    try:
        optimizer.optimize()
    except KeyboardInterrupt:
        print("\nOptimization interrupted!")
        optimizer.save_and_summarize()
    except Exception as e:
        print(f"Error: {e}")
        if optimizer.results:
            optimizer.save_and_summarize()

if __name__ == "__main__":
    main()