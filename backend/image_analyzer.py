import httpx
from PIL import Image
from io import BytesIO
import torch
import clip

# Load CLIP model once at startup (not on every request)
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# These are text descriptions of suspicious drug-related visuals.
# CLIP will check how closely the image matches these descriptions.
SUSPICIOUS_LABELS = [
    "white powder drugs",
    "pills and tablets",
    "marijuana cannabis",
    "drug paraphernalia syringe",
    "cash money bundles",
    "encrypted messaging drug deal",
]

SAFE_LABELS = [
    "food and cooking",
    "nature landscape",
    "people smiling",
    "sports and games",
]

ALL_LABELS = SUSPICIOUS_LABELS + SAFE_LABELS


async def analyze_image(image_url: str) -> dict:
    """
    Downloads the image from the URL and runs CLIP similarity check.
    Returns a score (0–40) and a flagged boolean.

    Score breakdown:
    - 0–15  : image looks safe
    - 16–30 : moderate suspicion
    - 31–40 : high suspicion
    """
    try:
        # Download image
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(image_url)
            response.raise_for_status()

        image = Image.open(BytesIO(response.content)).convert("RGB")

        # Preprocess image and encode text labels
        image_input = preprocess(image).unsqueeze(0).to(device)
        text_inputs  = clip.tokenize(ALL_LABELS).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            text_features  = model.encode_text(text_inputs)

        # Calculate similarity probabilities
        image_features /= image_features.norm(dim=-1, keepdim=True)
        text_features  /= text_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        probs = similarity[0].tolist()

        # Sum probability for all suspicious labels
        suspicious_score = sum(probs[:len(SUSPICIOUS_LABELS)]) * 100
        suspicious_score = min(suspicious_score, 40.0)  # cap contribution at 40

        return {
            "score": round(suspicious_score, 2),
            "flagged": suspicious_score > 20,
            "top_match": ALL_LABELS[probs.index(max(probs))]
        }

    except Exception as e:
        # If image fails to load, return zero score — don't crash
        return {"score": 0.0, "flagged": False, "error": str(e)}
