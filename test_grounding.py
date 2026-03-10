from agent2_schematizer import Agent2Schematizer
import json

def test_grounding():
    agent = Agent2Schematizer()
    
    test_plan = """
    1. Fill NoData in kerala_dem.tif
    2. Area calculations for boundary gadm41_IND_1.shp using raster proximity
    """
    
    # We use a file-based check since stdout can be tricky with encodings in sub-envs
    steps = agent.structure_plan(test_plan)
    
    with open("grounding_test_results.json", "w", encoding='utf-8') as f:
        json.dump(steps, f, indent=2)
    
    print("✅ Grounding results saved to grounding_test_results.json")

    
if __name__ == "__main__":
    test_grounding()
