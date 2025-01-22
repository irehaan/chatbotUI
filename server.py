from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
from typing import Optional
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration variables
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "9a651376-1593-4fec-ae77-58a912a5032e"
FLOW_ID = "01330d3c-d0e2-439c-a69f-8c6071ed99cf"

# Put your token here between the quotes
APPLICATION_TOKEN = "AstraCS:FeYitNOMPNQuEZHDoCCGpDca:84784d04bebbd576931b9df3499114dea1adf911a821eccda34d3b180d4910d4"

def validate_token():
    """Validate that the token is properly configured"""
    if not APPLICATION_TOKEN or APPLICATION_TOKEN.strip() == "":
        logger.error("Token is empty or not set")
        return False
    if "<" in APPLICATION_TOKEN or ">" in APPLICATION_TOKEN:
        logger.error("Token contains placeholder characters")
        return False
    return True

def run_flow(message: str,
    endpoint: str,
    output_type: str = "chat",
    input_type: str = "chat",
    application_token: Optional[str] = None) -> dict:
    """
    Run a flow with a given message.
    """
    try:
        api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{endpoint}"
        
        payload = {
            "input_value": message,
            "output_type": output_type,
            "input_type": input_type,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {application_token}"
        }
        
        logger.debug(f"Making request to API:")
        logger.debug(f"URL: {api_url}")
        logger.debug(f"Token length: {len(application_token) if application_token else 0}")
        logger.debug(f"Payload: {payload}")
        
        response = requests.post(api_url, json=payload, headers=headers)
        
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response content: {response.text[:100]}...")
        
        if response.status_code != 200:
            raise Exception(f"API returned status code {response.status_code}: {response.text}")
            
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise

@app.route('/')
def serve_html():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        logger.debug("Received chat request")
        
        if not validate_token():
            return jsonify({'error': 'Please set your application token in the server.py file'}), 500
            
        data = request.json
        logger.debug(f"Request data: {data}")
        
        message = data.get('message')
        endpoint = data.get('endpoint', FLOW_ID)
        output_type = data.get('output_type', 'chat')
        input_type = data.get('input_type', 'chat')
        
        response = run_flow(
            message=message,
            endpoint=endpoint,
            output_type=output_type,
            input_type=input_type,
            application_token=APPLICATION_TOKEN
        )
        
        logger.debug("Successfully processed request")
        return jsonify({
            'response': response
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if validate_token():
        logger.info("Token validation successful, starting server...")
        app.run(debug=True, port=5000)
    else:
        logger.error("Server not started due to token configuration issue")
        print("\n" + "="*50)
        print("ERROR: Please configure your application token!")
        print("Open server.py and paste your token in the APPLICATION_TOKEN variable")
        print("="*50 + "\n")
        