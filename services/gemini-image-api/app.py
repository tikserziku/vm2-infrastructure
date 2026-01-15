from flask import Flask, request, jsonify
import base64
import traceback
from google import genai
from google.genai import types

app = Flask(__name__)

GEMINI_API_KEY = "AIzaSyAXlZOVd0_igKYnNaQqJtBfQ4Ch-QGu9cc"

@app.route('/generate', methods=['POST'])
def generate_image():
    try:
        data = request.json
        prompt = data.get('prompt', 'A beautiful sunset')
        
        print(f"[GENERATE] Prompt: {prompt}")
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        model = "gemini-3-pro-image-preview"
        
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(
                image_size="1K",
            ),
        )
        
        print(f"[GENERATE] Calling model: {model}")
        
        # Stream
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.candidates is None:
                continue
            if chunk.candidates[0].content is None:
                continue
            if chunk.candidates[0].content.parts is None:
                continue
            
            for part in chunk.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    print(f"[GENERATE] Got image! Size: {len(part.inline_data.data)}")
                    image_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                    return jsonify({
                        "success": True,
                        "image": image_base64,
                        "mime_type": part.inline_data.mime_type
                    })
                elif part.text:
                    print(f"[GENERATE] Text: {part.text[:100]}")
        
        print("[GENERATE] No image in response")
        return jsonify({"success": False, "error": "No image generated"}), 500
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "models": ["gemini-3-pro-image-preview"]
    })

if __name__ == '__main__':
    print("Starting Gemini Image API on port 5680...")
    app.run(host='0.0.0.0', port=5680)

