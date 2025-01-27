from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import requests
from typing import Optional
import logging
import os
import traceback
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Enable CORS for all origins
CORS(app)

# Configuration variables
BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "9a651376-1593-4fec-ae77-58a912a5032e"
FLOW_ID = "01330d3c-d0e2-439c-a69f-8c6071ed99cf"

# Application token (hardcoded)
APPLICATION_TOKEN = "AstraCS:FeYitNOMPNQuEZHDoCCGpDca:84784d04bebbd576931b9df3499114dea1adf911a821eccda34d3b180d4910d4"

def validate_token():
    """Validate that the token is properly configured"""
    if not APPLICATION_TOKEN or APPLICATION_TOKEN.strip() == "":
        logger.error("Token is empty or not set")
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
        
        logger.info(f"Making request to API: {api_url}")
        logger.info(f"Payload: {payload}")
        
        response = requests.post(api_url, json=payload, headers=headers)
        
        # Log response details
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        logger.info(f"Response content: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code != 200:
            raise Exception(f"API returned status code {response.status_code}: {response.text}")
            
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error in run_flow: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def run_flow_stream(message: str,
    endpoint: str,
    output_type: str = "chat",
    input_type: str = "chat",
    application_token: Optional[str] = None):
    """
    Run a flow with streaming response.
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
            "Authorization": f"Bearer {application_token}",
            "Accept": "text/event-stream"
        }
        
        logger.info(f"Making streaming request to API: {api_url}")
        
        response = requests.post(api_url, json=payload, headers=headers, stream=True)
        
        if response.status_code != 200:
            raise Exception(f"API returned status code {response.status_code}: {response.text}")
        
        return response
    except Exception as e:
        logger.error(f"Unexpected error in run_flow_stream: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.route('/')
def serve_html():
    return send_from_directory('.', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        logger.info("Received chat request")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Log request body
        try:
            request_data = request.get_json()
            logger.info(f"Request body: {request_data}")
        except Exception as e:
            logger.error(f"Error parsing request body: {e}")
            return jsonify({'error': 'Invalid JSON'}), 400
        
        if not validate_token():
            return jsonify({'error': 'Application token not configured'}), 500
            
        data = request.json
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
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
        
        logger.info("Successfully processed request")
        return jsonify({
            'response': response
        })
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/chat-stream', methods=['POST'])
def chat_stream():
    try:
        logger.info("Received chat stream request")
        
        if not validate_token():
            return jsonify({'error': 'Application token not configured'}), 500
            
        data = request.json
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data.get('message')
        endpoint = data.get('endpoint', FLOW_ID)
        output_type = data.get('output_type', 'chat')
        input_type = data.get('input_type', 'chat')
        
        def generate():
            try:
                response = run_flow_stream(
                    message=message,
                    endpoint=endpoint,
                    output_type=output_type,
                    input_type=input_type,
                    application_token=APPLICATION_TOKEN
                )
                
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data: '):
                                try:
                                    json_data = json.loads(decoded_line[6:])
                                    
                                    # Extract the incremental text
                                    increment = ""
                                    if json_data.get('outputs', []) and len(json_data['outputs'][0].get('outputs', [])) > 0:
                                        chunk = json_data['outputs'][0]['outputs'][0]
                                        
                                        # Try different possible locations for the chunk
                                        if chunk.get('artifacts', {}).get('message'):
                                            increment = chunk['artifacts']['message']
                                        elif chunk.get('results', {}).get('message', {}).get('text'):
                                            increment = chunk['results']['message']['text']
                                    
                                    if increment:
                                        full_response += increment
                                        yield json.dumps({'content': increment}) + '\n\n'
                                except json.JSONDecodeError:
                                    logger.error(f"Could not parse JSON from line: {decoded_line}")
                        except Exception as parse_error:
                            logger.error(f"Error parsing stream line: {parse_error}")
            
                # Send full response as a final event
                yield json.dumps({'complete': True, 'content': full_response}) + '\n\n'
            
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                yield json.dumps({'error': str(e)}) + '\n\n'
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error processing stream request: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# Health check endpoint
@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if validate_token():
        logger.info("Token validation successful, starting server...")
        app.run(host='0.0.0.0', port=port)
    else:
        logger.error("Server not started due to token configuration issue")