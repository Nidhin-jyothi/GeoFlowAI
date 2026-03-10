"""
run_all_steps.py — Standalone QGIS Step Runner (without GUI)
Executes PyQGIS scripts sequentially from the outputs/ folder.
Each step must produce its output file to be considered successful.
"""

import subprocess
import os
import config

def run_qgis_steps(workflow_json_path=None):
    """
    Executes all steps in workflow_plan.json using the QGIS Python environment.
    Stops if any step fails (output file not created or ERROR printed).
    """
    import json

    if workflow_json_path is None:
        workflow_json_path = os.path.join(config.OUTPUT_DIR, "workflow_plan.json")

    if not os.path.exists(workflow_json_path):
        print(f"❌ Workflow JSON not found: {workflow_json_path}")
        return False

    with open(workflow_json_path, "r") as f:
        steps = json.load(f)

    print(f"🌐 Loaded {len(steps)} steps from {workflow_json_path}\n")

    QGIS_PYTHON = config.QGIS_PYTHON_EXECUTABLE
    BASE_DIR    = config.BASE_DIR

    for step in steps:
        sid         = step.get("step_id", "?")
        script_name = step.get("script_filename")
        output_file = step.get("output_file")
        script_path = os.path.join(config.OUTPUT_DIR, script_name)

        print(f"{'─'*60}")
        print(f"▶  {sid}  |  {step.get('algorithm')}  →  {script_name}")

        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            print("   Did Agent 3 generate it? Stopping.")
            return False

        env = os.environ.copy()
        env["CPL_LOG"] = "ERROR"  # Suppress GDAL log noise

        result = subprocess.run(
            [QGIS_PYTHON, script_path],
            capture_output=True,
            text=True,
            cwd=BASE_DIR,   # So relative paths like data/ and outputs/ work
            env=env
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        print(stdout)
        if stderr.strip():
            print("STDERR:", stderr[:500])

        # ── Strict success check ──────────────────────────────────
        script_errored = (
            "ERROR:" in stdout or
            "Traceback" in stdout or
            "Traceback" in stderr
        )
        script_succeeded = "SUCCESS" in stdout and not script_errored

        output_exists = False
        if output_file:
            out_path = output_file if os.path.isabs(output_file) else os.path.join(BASE_DIR, output_file)
            output_exists = os.path.exists(out_path)

        if script_succeeded and output_exists:
            print(f"✅ {sid} PASSED — output: {output_file}")
        else:
            print(f"❌ {sid} FAILED")
            if script_errored:
                print("   Reason: Script printed error/traceback")
            elif not script_succeeded:
                print("   Reason: Script did not print SUCCESS")
            elif not output_exists:
                print(f"   Reason: Output file missing: {output_file}")
            print("   Stopping pipeline.")
            return False

    print(f"\n{'═'*60}")
    print("✅ ALL STEPS COMPLETED SUCCESSFULLY")
    return True


if __name__ == "__main__":
    run_qgis_steps()