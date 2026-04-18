import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

# Load the environment variables from the .env file
load_dotenv()

class CrowdsourceVisionAgent:
    def __init__(self):
        # The genai.Client automatically looks for GEMINI_API_KEY in your environment
        api_key = os.getenv("GEMINI_API_KEY")
        
        # Safe defaults
        self.model_name = "gemini-1.5-flash"
        self.is_active = False
        self.client = None

        if not api_key:
            print("⚠️ GEMINI_API_KEY is missing. Vision features will be disabled.")
            return

        try:
            self.client = genai.Client()
            
            # --- The Architect's Dynamic Model Selector ---
            print("🔍 Auto-detecting the latest available Gemini Vision model...")
            valid_models = []
            # We wrap the list() call because this is where expired keys cause crashes
            for m in self.client.models.list():
                if "flash" in m.name:
                    valid_models.append(m.name)
                    
            if valid_models:
                # Select the most recent model Google returned
                self.model_name = valid_models[0]
                self.is_active = True
                print(f"✅ Dynamically connected to: {self.model_name}")
            else:
                print("⚠️ No Flash models found. Falling back to 'gemini-1.5-flash'.")
                # We still mark as inactive if discovery fails significantly, 
                # or keep it active if we trust the fallback. 
                # Let's be conservative:
                self.is_active = False 

        except Exception as e:
            print(f"❌ Vision Agent Initialization Failed: {e}")
            print("⚠️ Crowdsourcing features will be disabled until the API key is fixed.")
            self.is_active = False

    def analyze_price_tag(self, image_path: str):
        """
        Takes an image of a supermarket price tag and returns structured JSON data.
        """
        print(f"👁️ Vision Agent analyzing: {image_path}...")
        
        try:
            img = Image.open(image_path)
        except Exception as e:
            return {"error": f"Failed to open image: {e}"}

        # The Architect's Prompt
        prompt = """
        You are a highly accurate data extraction agent working for a Dutch supermarket application.
        Analyze this image of a price tag or receipt. 
        
        Extract the following information and return it STRICTLY as a JSON object:
        - "product_name": The name of the product (e.g., "AH Volle Melk").
        - "price": The discounted price as a float (e.g., 1.99). If no discount, use the regular price.
        - "deal_type": Try to classify the deal (e.g., "MULTI_BUY", "PERCENTAGE", "FIXED_PRICE", "UNKNOWN").
        - "confidence_score": An integer from 0 to 100 representing how confident you are in this extraction.

        If you cannot read the image, return a confidence_score of 0.
        """

        try:
            # Modern genai API structure using Structured Outputs
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, img],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            
            # Parse the JSON string returned by the model
            extracted_data = json.loads(response.text)
            return extracted_data
            
        except Exception as e:
            print(f"❌ Vision Agent Error: {e}")
            return {"error": "AI processing failed", "confidence_score": 0}

# --- ARCHITECT'S TEST SUITE ---
if __name__ == "__main__":
    agent = CrowdsourceVisionAgent()
    
    # Take a photo of a price tag or receipt, save it as 'test_tag.jpg' in this folder
    test_image = "test_tag.jpg" 
    
    # Create a dummy image if you just want to test if the API connects
    if not os.path.exists(test_image):
        print(f"⚠️ '{test_image}' not found. Creating a blank dummy image to test API connection...")
        Image.new('RGB', (100, 100), color = 'white').save(test_image)

    result = agent.analyze_price_tag(test_image)
    print("\n🧠 Agent Output:")
    print(json.dumps(result, indent=2))