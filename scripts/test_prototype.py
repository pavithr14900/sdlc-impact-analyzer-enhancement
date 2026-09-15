from sdlc.agents.prototype_agent import prototype_agent

state = {
    "requirement": "Build a customer management application to track customers, email, and status.",
    "requirement_analysis": "Summary of requirement analysis.",
    "user_stories": "## 2. USER STORIES\n\n- Story 1: ...",
    "design_standards": "",
}

result = prototype_agent(state)
print("Keys:", result.keys())
print("--- UI PROTOTYPE ---")
print(result.get("ui_prototype", "<empty>"))
print("--------------------")
