from agent1_planner import Agent1Planner
import os
import json

def test_grounded_planning():
    planner = Agent1Planner()
    query = "Identify flood prone areas in Kerala. Use the Boundary shp and the DEM."
    
    print("\n--- TESTING GROUNDED PLANNER (DATA-TYPE AWARE) ---")
    plan = planner.generate_plan(query)
    
    with open("test_grounded_plan.txt", "w", encoding='utf-8') as f:
        f.write(plan)
    
    print("✅ Grounded Plan saved to test_grounded_plan.txt")
    print("\n--- PLAN SUMMARY ---")
    print(plan[:1000] + "...")

if __name__ == "__main__":
    test_grounded_planning()

