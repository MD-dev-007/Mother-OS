# test_after_enable.py
import os
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel
import time

load_dotenv()

project_id = os.getenv('GOOGLE_PROJECT_ID', 'motheros')
region = 'us-central1'

print(f"🔧 Testing Vertex AI after enabling Generative AI...")
print(f"Project: {project_id}")
print(f"Region: {region}")
print("-" * 60)

input("\n⏳ Press ENTER after you've enabled Generative AI in Model Garden or Studio...")

print("\n⏳ Waiting 30 seconds for changes to propagate...")
time.sleep(30)

print("\n🧪 Testing API access...")

try:
    vertexai.init(project=project_id, location=region)
    model = GenerativeModel("gemini-1.5-flash")
    
    response = model.generate_content("Say hello in one sentence")
    
    print(f"\n✅ SUCCESS!")
    print("-" * 60)
    print(f"Response: {response.text}")
    print("-" * 60)
    
    print(f"\n📝 Your working configuration:")
    print(f"   LLM_PROVIDER=vertex")
    print(f"   GOOGLE_MODEL=gemini-1.5-flash")
    print(f"   GOOGLE_REGION=us-central1")
    print(f"   GOOGLE_PROJECT_ID={project_id}")
    
    print("\n🎉 MotherOS is ready to use Vertex AI with free trial credits!")
    
except Exception as e:
    print(f"\n❌ Still failing: {str(e)[:200]}")
    print("\n📧 Contact Google Support with this info:")
    print(f"   - Error: 404 Publisher Model not found")
    print(f"   - Project: {project_id}")
    print(f"   - Need: Vertex AI Generative AI access enabled")