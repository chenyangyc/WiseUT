import json
import argparse
from main_utils import add_module_path, run_with_interpreter

    
def main(config):
    parser = argparse.ArgumentParser(description="Run specific module with config.")
    parser.add_argument("--config", required=True, help="Path to config file.")
    parser.add_argument(
        "--module",
        required=True,
        choices=["coverage", "refine", "defect"],
        help="Which module to run.",
    )
    args = parser.parse_args()

    if args.module == "coverage":
        add_module_path('coverage_module')
        from coverage_module.starter_mvn import coverage_entry  # entry for coverage
        from coverage_module.collect_coverage import collect_cov  # utils for collect cov

        coverage_entry()
        collect_cov()

    elif args.module == "refine":
        add_module_path('refine_module')
        run_with_interpreter(config['refine_env'], "main", "refine_tests")
    
    elif args.module == 'defect':
        add_module_path('defect_module')
        from defect_module.extract_focal_method import type_error_extract_focal_method_entry
        type_error_extract_focal_method_entry()
        
        run_with_interpreter(config['defect_env'], "run_generation", "type_error_detection_entry")

if __name__ == "__main__":
    with open('./main_config.json', 'r') as fr:
        config = json.loads(fr.read())
    main(config)