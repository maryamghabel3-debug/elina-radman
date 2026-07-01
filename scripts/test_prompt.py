from agents.prompt_engineer import PromptEngineerAgent

agent = PromptEngineerAgent()
print("============== PHOTO PROMPT ==============")
photo = agent.generate_photo_prompt("sitting at a dark wooden table drinking espresso", tone="Dark Cinematic")
print(photo)

print("\n============== VIDEO JSON SCRIPT ==============")
video = agent.generate_cinematic_json_script("pulling a tarot card from the deck with intense focus", tone="mysterious")
print(video)
