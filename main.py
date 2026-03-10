import sys
import json
import os
import argparse
from agent1_planner import Agent1Planner
from agent2_schematizer import Agent2Schematizer
from agent3_codegen import Agent3CodeGen
from agent4_run_debug import Agent4Debugger
import config

def main():
    parser = argparse.ArgumentParser(description="GeoFlowAI: Natural Language to QGIS Workflow")
    parser.add_argument("query", help="The geospatial query to execute.")
    parser.add_argument("--plan-only", action="store_true", help="Generate plan but do not execute.")
    args = parser.parse_args()

    # Initialize Agents
    planner = Agent1Planner()
    schematizer = Agent2Schematizer()
    codegen = Agent3CodeGen()
    runner = Agent4Debugger()

    print(f"🌍 GeoFlowAI: {args.query}")
    
    # 1. PLAN
    print("\n🧠 Agent 1: Planning...")
    plan_text = planner.generate_plan(args.query)
    print(f"Plan Generated ({len(plan_text)} chars).")
    # print(plan_text) 

    # 2. STRUCTURE
    print("\n📋 Agent 2: Structuring...")
    steps = schematizer.structure_plan(plan_text)
    
    if not steps:
        print("❌ Failed to structure plan.")
        return

    print(f"Structured {len(steps)} steps.")
    
    # Save plan for debugging
    with open(os.path.join(config.OUTPUT_DIR, "workflow_plan.json"), "w") as f:
        json.dump(steps, f, indent=2)

    if args.plan_only:
        print("Plan saved to outputs/workflow_plan.json")
        return

    # 3. GENERATE & EXECUTE LOOP
    print("\n⚙️ Agent 3 & 4: Generating and Executing Code...")
    
    for i, step in enumerate(steps):
        step_id = step.get("step_id", f"step_{i}")
        name = step.get("name", "unnamed_step")
        print(f"\n🔹 Step {i+1}: {name}")
        
        # Generate Code
        code = codegen.generate_code(step)
        if not code:
            print(f"❌ Failed to generate code for step {name}")
            break
            
        # Save Script
        filename = step.get("script_filename", f"script_{i}.py")
        script_path = os.path.join(config.BASE_DIR, filename)
        
        with open(script_path, "w") as f:
            f.write(code)
            
        print(f"💾 Saved script: {filename}")
        
        # Execute (Agent 4)
        inputs = step.get("input_files", [])
        output = step.get("output_file", "")
        
        success = runner.run_step(script_path, inputs, output)
        
        if not success:
            print(f"⛔ Workflow stopped at step {name}.")
            break
            
    print("\n✅ Workflow Completed.")

if __name__ == "__main__":
    main()
