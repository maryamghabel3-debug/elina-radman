"""Single source of truth for content pillars, hashtags and brand voice.

Both `scripts/generate.py` (GitHub Actions daily job) and
`agents/content_creator.py` (bot / dashboard / MCP) import from here so the two
generation paths stay consistent instead of drifting apart.
"""

BRAND = 'Elina Radman | Petite Quiet Luxury | 4\'11" (150cm) | 43kg'
TONE = "warm, sophisticated, relatable, like a stylish best friend"
AUDIENCE = "petite women 18-35 who want to look expensive on a budget"

# The canonical content pillars for Elina.
PILLARS = [
    "petite_styling",
    "ootd",
    "capsule_wardrobe",
    "smart_shopping",
    "lifestyle",
    "ai_tech_hacks",
    "psychology_of_style",
    "horticulture_and_growth",
]

# Per-pillar hashtag sets.
TAGS = {
    "petite_styling": "#PetiteStyle #StyleTips #ShortGirlFashion #FashionHacks #LookTaller",
    "ootd": "#OOTD #OutfitOfTheDay #PetiteStyle #QuietLuxury #4ft11",
    "capsule_wardrobe": "#CapsuleWardrobe #MinimalistStyle #PetiteStyle #WardrobeEssentials",
    "smart_shopping": "#AffordableStyle #SmartShopping #PetiteHaul #QuietLuxury",
    "lifestyle": "#DayInMyLife #PetiteStyle #QuietLuxury #LifeStyleCreator",
    "ai_tech_hacks": "#AITech #TechTips #OutfitPlanner #TechGirl",
    "psychology_of_style": "#FashionPsychology #Confidence #MentalHealth #Mindset",
    "horticulture_and_growth": "#Horticulture #PlantTherapy #NatureLover #Growth",
}

# Appended to every post.
BASE_TAGS = "#StyledByElina #PetiteFashion"

# Curated offline fallback captions (used when no LLM key is configured) so the
# pipeline never emits placeholder text.
FALLBACK_CAPTIONS = {
    "petite_styling": "3 style rules every petite needs 🕊️\n\n1. High-waisted everything — elongates legs\n2. Monochrome outfits — no visual break\n3. Tailor everything\n\nWhich rule do you already follow? 👇",
    "ootd": "Today's OOTD: Quiet Luxury 🕊️\n\nCropped camel blazer + high-waist trousers\nEvery piece tailored for 4'11\" ✨\n\nWhat are you wearing today? 👇",
    "capsule_wardrobe": "15 pieces = 30+ outfits 🤍\n\n3 bottoms + 4 tops + 2 blazers + 2 dresses\nAll neutral. Everything matches.\n\nComment CAPSULE for the list 📩",
    "smart_shopping": "Look expensive without the price tag 💰\n\nNatural fabrics · neutral palette · tailor everything.\n\nYour best budget style tip? 👇",
    "lifestyle": "A day in my outfits ☕\n\nSame base pieces, three different looks.\nThis is capsule wardrobe magic ✨\n\nWhat does your day look like? 👇",
    "ai_tech_hacks": "The app that plans my outfits for the week 🤖\n\nI feed it my capsule pieces and it mixes new looks.\nTech + style = less decision fatigue ✨\n\nWant the name? Comment TECH 👇",
    "psychology_of_style": "What you wear rewires how you feel 🧠\n\n'Enclothed cognition' is real — a sharp blazer literally\nmakes you think sharper.\n\nWhat outfit makes YOU feel powerful? 👇",
    "horticulture_and_growth": "Slow growth is still growth 🌱\n\nTending plants taught me patience I bring to everything.\nStyle, like a garden, is built season by season.\n\nWhat are you growing right now? 👇",
}


def tags_for(pillar: str) -> str:
    """Full hashtag string for a pillar (pillar tags + base tags)."""
    return f"{TAGS.get(pillar, '')} {BASE_TAGS}".strip()


def fallback_for(pillar: str) -> str:
    """Curated caption for a pillar, defaulting to the OOTD one."""
    return FALLBACK_CAPTIONS.get(pillar, FALLBACK_CAPTIONS["ootd"])
